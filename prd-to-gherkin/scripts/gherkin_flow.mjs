import { createHash } from 'node:crypto'
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from 'node:fs'
import { dirname, join, resolve } from 'node:path'

import * as gherkin from '@cucumber/gherkin'
import * as messages from '@cucumber/messages'

import { containsUnresolvedUnknown } from './feature_semantic_markers.mjs'

export const ARTIFACT_SCHEMA_VERSION = 'testcases/v2'
export const FEATURE_FORMAT_VERSION = 'feature/v2'
export const BUNDLE_FILES = Object.freeze([
  'testcases.json',
  'testcases.feature',
  'testcases_manifest.json',
  'validation_report.json',
  'quality_report.md',
])

const KIND_ORDER = Object.freeze({ main: 0, boundary: 1, exception: 2, nfr: 3 })
const PHASE_ORDER = Object.freeze({ given: 0, when: 1, then: 2 })
const TESTCASE_KEYS = Object.freeze([
  'tc_id', 'scenario_id', 'acceptance_contract_id', 'requirement_ids', 'source_kinds',
  'kind', 'source_index', 'title', 'render_mode', 'test_obligation', 'steps', 'evidence_refs',
])
const STEP_KEYS = Object.freeze(['phase', 'keyword', 'text', 'source_field', 'source_index'])
const OBLIGATION_KEYS = Object.freeze([
  'kind', 'source_acceptance_contract_id', 'source_fields', 'evidence_refs',
])
const RENDER_CONTRACT = Object.freeze({
  feature_format_version: FEATURE_FORMAT_VERSION,
  encoding: 'UTF-8',
  unicode_normalization: 'NFC',
  line_ending: 'LF',
  terminal_newline: true,
  keyword_language: 'en',
  background: 'FORBIDDEN',
  scenario_outline: 'FORBIDDEN_IN_PRD_V3',
  doc_string: 'FORBIDDEN',
  data_table: 'FORBIDDEN',
  tag_order: ['requirement_ids', 'tc_id'],
  scenario_order: ['acceptance_contract_id', 'kind', 'source_index', 'tc_id'],
})
const ENVELOPE_KEYS = Object.freeze([
  'schema_version',
  'artifact_schema_version',
  'run_id',
  'project_id',
  'node_id',
  'parent_node_id',
  'artifact_id',
  'artifact_type',
  'created_at',
  'generator',
  'status',
  'input_artifacts',
  'requirement_ids',
  'source_prd',
  'render_contract',
  'testcases',
  'blocked_items',
])

function compareAscii(left, right) {
  return left < right ? -1 : left > right ? 1 : 0
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function normalizedText(value, label) {
  if (typeof value !== 'string') throw new Error(`${label} must be a string`)
  const normalized = value.normalize('NFC').replace(/\s+/gu, ' ').trim()
  if (!normalized) throw new Error(`${label} must not be empty`)
  return normalized
}

function normalizedList(value, label) {
  const items = asArray(value)
  if (!items.length) throw new Error(`${label} must contain at least one item`)
  return items.map((item, index) => normalizedText(item, `${label}[${index}]`))
}

function uniqueSorted(items) {
  return [...new Set(items)].sort(compareAscii)
}

function sha256Bytes(value) {
  return createHash('sha256').update(value).digest('hex')
}

export function canonicalJson(value) {
  return `${JSON.stringify(value, null, 2)}\n`.normalize('NFC').replace(/\r\n?/gu, '\n')
}

function assertExactKeys(value, expected, label) {
  const actual = Object.keys(value)
  const missing = expected.filter((key) => !actual.includes(key))
  const extra = actual.filter((key) => !expected.includes(key))
  if (missing.length || extra.length) {
    throw new Error(`${label} keys differ; missing=[${missing}], extra=[${extra}]`)
  }
}

function validateReadyPrd(prd) {
  const errors = []
  if (!prd || typeof prd !== 'object' || Array.isArray(prd)) errors.push('PRD root must be an object')
  if (prd?.schema_version !== '1.0') errors.push('PRD schema_version must be 1.0')
  if (prd?.artifact_schema_version !== 'prd/v3') errors.push('PRD artifact_schema_version must be prd/v3')
  if (prd?.status !== 'PASS') errors.push('PRD status must be PASS')
  if (!['approved', 'complete'].includes(prd?.prd_status)) errors.push('PRD prd_status must be approved or complete')
  const payload = prd?.payload
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) errors.push('PRD payload must be an object')
  const document = payload?.document
  if (document?.ready_for_test_generation !== true) errors.push('PRD is not ready_for_test_generation')
  if (document?.oracle_blocked_count !== 0) errors.push('PRD oracle_blocked_count must be 0')
  if (asArray(payload?.blocking_questions).length) errors.push('PRD has blocking_questions')

  const requirements = asArray(payload?.requirements)
  const ids = requirements.map((item) => item?.id)
  if (!requirements.length) errors.push('PRD must contain requirements')
  if (ids.some((id) => typeof id !== 'string' || !/^(?:REQ|NFR)-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$/.test(id))) {
    errors.push('PRD contains an invalid requirement ID')
  }
  if (new Set(ids).size !== ids.length) errors.push('PRD requirement IDs must be unique')
  if (prd?.requirement_ids && JSON.stringify(prd.requirement_ids) !== JSON.stringify(ids)) {
    errors.push('PRD requirement_ids must match payload order')
  }
  const current = requirements.filter((item) => item?.release_scope === 'current')
  if (!current.length) errors.push('PRD must contain at least one current requirement')
  for (const requirement of current) {
    if (requirement.requirement_kind !== 'atomic') errors.push(`${requirement.id} must be atomic`)
    if (!['explicit', 'valid_derivation'].includes(requirement.source_kind)) {
      errors.push(`${requirement.id} has invalid source_kind`)
    }
    if (!asArray(requirement.evidence_refs).length) errors.push(`${requirement.id} has no evidence_refs`)
  }

  const currentIds = new Set(current.map((item) => item.id))
  const ledger = asArray(payload?.oracle_coverage_ledger)
  const ledgerById = new Map(ledger.map((item) => [item?.requirement_id, item]))
  for (const requirementId of currentIds) {
    const row = ledgerById.get(requirementId)
    if (!row || row.status !== 'ready') errors.push(`${requirementId} has no ready oracle ledger row`)
    if (!asArray(row?.acceptance_contract_ids).length) errors.push(`${requirementId} has no acceptance contract`) 
  }

  const contracts = asArray(payload?.acceptance_contracts)
  const contractIds = contracts.map((item) => item?.id)
  if (new Set(contractIds).size !== contractIds.length) errors.push('acceptance contract IDs must be unique')
  const relevantContracts = contracts.filter(
    (item) => item?.release_scope === 'current' && asArray(item?.verifies).some((id) => currentIds.has(id)),
  )
  if (!relevantContracts.length) errors.push('PRD has no current acceptance contracts')
  for (const contract of relevantContracts) {
    if (!/^AC-(?:REQ|NFR)-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*-[0-9]{2}$/.test(contract.id ?? '')) {
      errors.push(`${String(contract.id)} has invalid acceptance contract ID`)
    }
    if (!['functional', 'nfr'].includes(contract.type)) errors.push(`${contract.id} has invalid type`)
    const verifies = asArray(contract.verifies)
    if (!verifies.length || verifies.some((id) => !currentIds.has(id))) {
      errors.push(`${contract.id} must verify current requirements only`)
    }
    if (!asArray(contract.evidence_refs).length) errors.push(`${contract.id} has no evidence_refs`)
    if (contract.type === 'functional') {
      for (const field of ['actor', 'trigger']) {
        if (typeof contract[field] !== 'string' || !contract[field].trim()) errors.push(`${contract.id} missing ${field}`)
      }
      for (const field of ['preconditions', 'response', 'observable_oracles', 'boundaries', 'exceptions']) {
        if (!asArray(contract[field]).length) errors.push(`${contract.id} missing ${field}`)
      }
      for (const field of ['boundaries', 'exceptions']) {
        asArray(contract[field]).forEach((item, index) => {
          if (!item?.condition || !item?.response) errors.push(`${contract.id} incomplete ${field}[${index}]`)
        })
      }
    } else {
      for (const field of ['population', 'measurement_start', 'measurement_end', 'unit', 'threshold', 'pass_rule']) {
        if (typeof contract[field] !== 'string' || !contract[field].trim()) errors.push(`${contract.id} missing ${field}`)
      }
      if (!asArray(contract.exclusions).length) errors.push(`${contract.id} missing exclusions`)
    }
  }
  if (errors.length) throw new Error(`GENERATION_BLOCKED:\n- ${errors.join('\n- ')}`)
  return { payload, current, relevantContracts }
}

function step(phase, keyword, text, sourceField, sourceIndex = null) {
  return {
    phase,
    keyword,
    text: normalizedText(text, sourceField),
    source_field: sourceField,
    source_index: sourceIndex,
  }
}

function functionalBaseSteps(contract) {
  const given = [step('given', 'Given', `actor: ${contract.actor}`, 'actor')]
  normalizedList(contract.preconditions, `${contract.id}.preconditions`).forEach((text, index) => {
    given.push(step('given', 'And', `precondition: ${text}`, 'preconditions', index))
  })
  return given
}

function functionalCases(contract) {
  const cases = []
  const base = functionalBaseSteps(contract)
  const mainThen = []
  normalizedList(contract.response, `${contract.id}.response`).forEach((text, index) => {
    mainThen.push(step('then', index === 0 ? 'Then' : 'And', `response: ${text}`, 'response', index))
  })
  normalizedList(contract.observable_oracles, `${contract.id}.observable_oracles`).forEach((text, index) => {
    mainThen.push(step('then', 'And', `observable oracle: ${text}`, 'observable_oracles', index))
  })
  cases.push({
    kind: 'main',
    sourceIndex: 0,
    steps: [...base, step('when', 'When', contract.trigger, 'trigger'), ...mainThen],
    sourceFields: ['actor', 'preconditions', 'trigger', 'response', 'observable_oracles'],
  })
  for (const [index, boundary] of asArray(contract.boundaries).entries()) {
    cases.push({
      kind: 'boundary',
      sourceIndex: index,
      steps: [
        ...base,
        step('given', 'And', `boundary condition: ${boundary.condition}`, 'boundaries.condition', index),
        step('when', 'When', contract.trigger, 'trigger'),
        step('then', 'Then', `boundary response: ${boundary.response}`, 'boundaries.response', index),
      ],
      sourceFields: ['actor', 'preconditions', 'trigger', `boundaries[${index}]`],
    })
  }
  for (const [index, exception] of asArray(contract.exceptions).entries()) {
    cases.push({
      kind: 'exception',
      sourceIndex: index,
      steps: [
        ...base,
        step('given', 'And', `exception condition: ${exception.condition}`, 'exceptions.condition', index),
        step('when', 'When', contract.trigger, 'trigger'),
        step('then', 'Then', `exception response: ${exception.response}`, 'exceptions.response', index),
      ],
      sourceFields: ['actor', 'preconditions', 'trigger', `exceptions[${index}]`],
    })
  }
  return cases
}

function nfrCases(contract) {
  const given = [step('given', 'Given', `population: ${contract.population}`, 'population')]
  normalizedList(contract.exclusions, `${contract.id}.exclusions`).forEach((text, index) => {
    given.push(step('given', 'And', `exclusion: ${text}`, 'exclusions', index))
  })
  return [{
    kind: 'nfr',
    sourceIndex: 0,
    steps: [
      ...given,
      step(
        'when',
        'When',
        `measurement window: ${contract.measurement_start} -> ${contract.measurement_end}`,
        'measurement_start+measurement_end',
      ),
      step('then', 'Then', `pass rule: ${contract.pass_rule}`, 'pass_rule'),
      step('then', 'And', `threshold: ${contract.threshold}`, 'threshold'),
      step('then', 'And', `unit: ${contract.unit}`, 'unit'),
    ],
    sourceFields: [
      'population', 'exclusions', 'measurement_start', 'measurement_end', 'pass_rule', 'threshold', 'unit',
    ],
  }]
}

function suffix(kind, sourceIndex) {
  if (kind === 'main' || kind === 'nfr') return kind.toUpperCase()
  return `${kind.toUpperCase()}-${String(sourceIndex + 1).padStart(2, '0')}`
}

function buildTestcase(contract, contractCase, requirementIndex) {
  const requirementIds = uniqueSorted(contract.verifies)
  const sourceKinds = uniqueSorted(requirementIds.map((id) => requirementIndex.get(id).source_kind))
  const requirementEvidence = requirementIds.flatMap((id) => asArray(requirementIndex.get(id).evidence_refs))
  const evidenceRefs = uniqueSorted([...requirementEvidence, ...asArray(contract.evidence_refs)])
  const tcId = `TC-${contract.id}-${suffix(contractCase.kind, contractCase.sourceIndex)}`
  return {
    tc_id: tcId,
    scenario_id: `SC-${tcId.slice(3)}`,
    acceptance_contract_id: contract.id,
    requirement_ids: requirementIds,
    source_kinds: sourceKinds,
    kind: contractCase.kind,
    source_index: contractCase.sourceIndex,
    title: `[${contract.id}][${contractCase.kind}${contractCase.kind === 'main' || contractCase.kind === 'nfr' ? '' : `-${String(contractCase.sourceIndex + 1).padStart(2, '0')}`}]`,
    render_mode: 'SCENARIO',
    test_obligation: {
      kind: contractCase.kind,
      source_acceptance_contract_id: contract.id,
      source_fields: contractCase.sourceFields,
      evidence_refs: evidenceRefs,
    },
    steps: contractCase.steps,
    evidence_refs: evidenceRefs,
  }
}

export function compilePrd(prd, sourceBytes) {
  const { current, relevantContracts } = validateReadyPrd(prd)
  const requirementIndex = new Map(current.map((item) => [item.id, item]))
  const testcases = []
  for (const contract of [...relevantContracts].sort((a, b) => compareAscii(a.id, b.id))) {
    const cases = contract.type === 'functional' ? functionalCases(contract) : nfrCases(contract)
    for (const contractCase of cases) testcases.push(buildTestcase(contract, contractCase, requirementIndex))
  }
  testcases.sort((left, right) =>
    compareAscii(left.acceptance_contract_id, right.acceptance_contract_id) ||
    KIND_ORDER[left.kind] - KIND_ORDER[right.kind] ||
    left.source_index - right.source_index ||
    compareAscii(left.tc_id, right.tc_id),
  )
  const sourceHash = sha256Bytes(sourceBytes)
  return {
    schema_version: '1.0',
    artifact_schema_version: ARTIFACT_SCHEMA_VERSION,
    run_id: prd.run_id,
    project_id: prd.project_id,
    node_id: prd.node_id,
    parent_node_id: prd.parent_node_id ?? null,
    artifact_id: `${prd.artifact_id}:testcases`,
    artifact_type: 'testcases',
    created_at: prd.created_at,
    generator: 'prd-to-gherkin',
    status: 'PASS',
    input_artifacts: [prd.artifact_id],
    requirement_ids: uniqueSorted(current.map((item) => item.id)),
    source_prd: {
      artifact_id: prd.artifact_id,
      artifact_schema_version: prd.artifact_schema_version,
      sha256: sourceHash,
    },
    render_contract: structuredClone(RENDER_CONTRACT),
    testcases,
    blocked_items: [],
  }
}

export function renderFeature(model) {
  const lines = [
    `# artifact_schema_version: ${model.artifact_schema_version}`,
    `# source_prd_artifact_id: ${model.source_prd.artifact_id}`,
    `# source_prd_sha256: ${model.source_prd.sha256}`,
    `Feature: ${normalizedText(model.project_id, 'project_id')} acceptance tests`,
  ]
  for (const testcase of model.testcases) {
    lines.push(
      '',
      `  # ${testcase.scenario_id}`,
      `  # acceptance_contract_id: ${testcase.acceptance_contract_id}`,
      `  ${[...testcase.requirement_ids.map((id) => `@${id}`), `@${testcase.tc_id}`].join(' ')}`,
      `  Scenario: ${testcase.title}`,
    )
    for (const item of testcase.steps) lines.push(`    ${item.keyword} ${item.text}`)
  }
  return `${lines.join('\n')}\n`.normalize('NFC')
}

function parseFeature(featureText) {
  const builder = new gherkin.AstBuilder(messages.IdGenerator.incrementing())
  const matcher = new gherkin.GherkinClassicTokenMatcher()
  const parser = new gherkin.Parser(builder, matcher)
  return parser.parse(featureText)
}

export function validateProjection(model, featureText) {
  const errors = []
  try {
    assertExactKeys(model, ENVELOPE_KEYS, 'testcases model')
  } catch (error) {
    errors.push(error.message)
  }
  if (model?.schema_version !== '1.0') errors.push('schema_version must be 1.0')
  if (model?.artifact_schema_version !== ARTIFACT_SCHEMA_VERSION) errors.push(`artifact_schema_version must be ${ARTIFACT_SCHEMA_VERSION}`)
  if (model?.artifact_type !== 'testcases' || model?.status !== 'PASS') errors.push('artifact_type/status must be testcases/PASS')
  if (JSON.stringify(model?.render_contract) !== JSON.stringify(RENDER_CONTRACT)) errors.push('render_contract drift')
  const seenTc = new Set()
  const seenScenario = new Set()
  for (const testcase of asArray(model?.testcases)) {
    try {
      assertExactKeys(testcase, TESTCASE_KEYS, testcase.tc_id ?? 'testcase')
      assertExactKeys(testcase.test_obligation ?? {}, OBLIGATION_KEYS, `${testcase.tc_id}.test_obligation`)
      for (const [index, item] of asArray(testcase.steps).entries()) {
        assertExactKeys(item, STEP_KEYS, `${testcase.tc_id}.steps[${index}]`)
      }
    } catch (error) {
      errors.push(error.message)
    }
    if (seenTc.has(testcase.tc_id)) errors.push(`duplicate tc_id ${testcase.tc_id}`)
    if (seenScenario.has(testcase.scenario_id)) errors.push(`duplicate scenario_id ${testcase.scenario_id}`)
    seenTc.add(testcase.tc_id)
    seenScenario.add(testcase.scenario_id)
    if (testcase.render_mode !== 'SCENARIO') errors.push(`${testcase.tc_id} render_mode must be SCENARIO`)
    const phases = testcase.steps.map((item) => item.phase)
    const whenCount = phases.filter((phase) => phase === 'when').length
    if (!phases.includes('given') || !phases.includes('then') || whenCount !== 1) {
      errors.push(`${testcase.tc_id} must have 1+ Given, exactly 1 When, and 1+ Then`)
    }
    let lastPhase = 'given'
    for (const [index, item] of testcase.steps.entries()) {
      if (!['given', 'when', 'then'].includes(item.phase)) errors.push(`${testcase.tc_id} step ${index} invalid phase`)
      if (PHASE_ORDER[item.phase] < PHASE_ORDER[lastPhase]) errors.push(`${testcase.tc_id} step phase order drift`)
      lastPhase = item.phase
    }
    const given = testcase.steps.filter((item) => item.phase === 'given')
    const when = testcase.steps.filter((item) => item.phase === 'when')
    const then = testcase.steps.filter((item) => item.phase === 'then')
    if (given[0]?.keyword !== 'Given' || given.slice(1).some((item) => item.keyword !== 'And')) errors.push(`${testcase.tc_id} Given/And sequence drift`)
    if (when[0]?.keyword !== 'When') errors.push(`${testcase.tc_id} When keyword drift`)
    if (then[0]?.keyword !== 'Then' || then.slice(1).some((item) => item.keyword !== 'And')) errors.push(`${testcase.tc_id} Then/And sequence drift`)
    if (!testcase.test_obligation?.source_acceptance_contract_id || !asArray(testcase.test_obligation?.evidence_refs).length) {
      errors.push(`${testcase.tc_id} has no evidence-backed test_obligation`)
    }
  }
  let expectedFeature = null
  try {
    expectedFeature = renderFeature(model)
  } catch (error) {
    errors.push(`Feature rendering failed: ${error.message}`)
  }
  if (expectedFeature === null || featureText !== expectedFeature) errors.push('Feature differs from byte-deterministic renderer output')
  if (featureText !== featureText.normalize('NFC')) errors.push('Feature is not NFC')
  if (/\r/u.test(featureText) || !featureText.endsWith('\n')) errors.push('Feature must use LF and one terminal newline')
  if (/^\s*(?:Background|Scenario Outline|Examples)\s*:/mu.test(featureText)) errors.push('Background/Outline/Examples are forbidden in feature/v2')
  if (/\bHYP-[A-Za-z0-9-]+\b/u.test(featureText)) errors.push('HYPOTHESIS identifier leaked into Feature')
  if (containsUnresolvedUnknown(featureText)) errors.push('unresolved UNKNOWN leaked into Feature')
  try {
    parseFeature(featureText)
  } catch (error) {
    errors.push(`official Gherkin parser rejected Feature: ${error.message}`)
  }
  return {
    schema_version: '1.0',
    artifact_schema_version: 'testcases-validation/v2',
    validator: 'prd-to-gherkin',
    status: errors.length ? 'STRUCTURE_FAIL' : 'STRUCTURE_PASS',
    checks: {
      canonical_model: errors.filter((item) => !item.startsWith('Feature') && !item.includes('Gherkin')).length === 0,
      byte_deterministic_projection: expectedFeature !== null && featureText === expectedFeature,
      official_gherkin_parser: !errors.some((item) => item.includes('Gherkin parser')),
      mocktest_strict: 'NOT_RUN',
    },
    counts: {
      requirements: asArray(model?.requirement_ids).length,
      testcases: asArray(model?.testcases).length,
      scenarios: asArray(model?.testcases).length,
    },
    errors,
    scope: {
      proves: ['canonical testcase structure', 'byte-exact Feature projection', 'Gherkin syntax'],
      does_not_prove: ['natural-language semantic equivalence', 'Mocktest strict business PASS'],
    },
  }
}

function renderQuality(model, validation) {
  const kinds = Object.fromEntries(Object.keys(KIND_ORDER).map((kind) => [kind, model.testcases.filter((item) => item.kind === kind).length]))
  return [
    '# Testcase Generation Quality Report',
    '',
    '## 1. Artifact Identity',
    '',
    `- Schema: ${model.artifact_schema_version}`,
    `- Artifact: ${model.artifact_id}`,
    `- Source PRD: ${model.source_prd.artifact_id}`,
    '',
    '## 2. Generation Result',
    '',
    `- Structure status: ${validation.status}`,
    '- Mocktest strict status: NOT_RUN',
    `- Requirements: ${validation.counts.requirements}`,
    `- Testcases: ${validation.counts.testcases}`,
    '',
    '## 3. Scenario Kinds',
    '',
    ...Object.entries(kinds).map(([kind, count]) => `- ${kind}: ${count}`),
    '',
    '## 4. Blocking Items',
    '',
    ...(model.blocked_items.length ? model.blocked_items.map((item) => `- ${item}`) : ['- None']),
    '',
    '## 5. Validation Boundary',
    '',
    '- STRUCTURE_PASS does not mean Mocktest strict PASS.',
    '- Feature content is a deterministic view of testcases.json.',
    '',
  ].join('\n')
}

export function buildBundle(prdPath, outputDirectory) {
  const sourcePath = resolve(prdPath)
  const outputPath = resolve(outputDirectory)
  if (existsSync(outputPath)) throw new Error(`output directory already exists: ${outputPath}`)
  const sourceBytes = readFileSync(sourcePath)
  const prd = JSON.parse(sourceBytes.toString('utf8'))
  const model = compilePrd(prd, sourceBytes)
  const featureText = renderFeature(model)
  const validation = validateProjection(model, featureText)
  if (validation.status !== 'STRUCTURE_PASS') {
    throw new Error(`GENERATION_BLOCKED:\n- ${validation.errors.join('\n- ')}`)
  }
  const modelText = canonicalJson(model)
  const validationWithHashes = {
    ...validation,
    source_prd_sha256: model.source_prd.sha256,
    testcases_sha256: sha256Bytes(Buffer.from(modelText, 'utf8')),
    feature_sha256: sha256Bytes(Buffer.from(featureText, 'utf8')),
  }
  const validationText = canonicalJson(validationWithHashes)
  const qualityText = renderQuality(model, validationWithHashes)
  const manifest = {
    schema_version: '1.0',
    artifact_schema_version: 'testcases-bundle/v2',
    artifact_id: `${model.artifact_id}:manifest`,
    artifact_type: 'testcases_bundle_manifest',
    status: 'STRUCTURE_PASS',
    source_prd: {
      artifact_id: model.source_prd.artifact_id,
      sha256: model.source_prd.sha256,
    },
    files: [
      { path: 'testcases.json', sha256: sha256Bytes(Buffer.from(modelText, 'utf8')) },
      { path: 'testcases.feature', sha256: sha256Bytes(Buffer.from(featureText, 'utf8')) },
      { path: 'validation_report.json', sha256: sha256Bytes(Buffer.from(validationText, 'utf8')) },
      { path: 'quality_report.md', sha256: sha256Bytes(Buffer.from(qualityText, 'utf8')) },
    ],
    bundle_files: [...BUNDLE_FILES],
    strict_execution_status: 'NOT_RUN',
  }
  mkdirSync(dirname(outputPath), { recursive: true })
  const temporaryPath = mkdtempSync(join(dirname(outputPath), '.testcases-tmp-'))
  writeFileSync(join(temporaryPath, 'testcases.json'), modelText, 'utf8')
  writeFileSync(join(temporaryPath, 'testcases.feature'), featureText, 'utf8')
  writeFileSync(join(temporaryPath, 'validation_report.json'), validationText, 'utf8')
  writeFileSync(join(temporaryPath, 'quality_report.md'), qualityText, 'utf8')
  writeFileSync(join(temporaryPath, 'testcases_manifest.json'), canonicalJson(manifest), 'utf8')
  renameSync(temporaryPath, outputPath)
  return { outputPath, model, featureText, validation: validationWithHashes, manifest }
}

export function validateBundle(bundleDirectory) {
  const directory = resolve(bundleDirectory)
  const modelText = readFileSync(join(directory, 'testcases.json'), 'utf8')
  const featureText = readFileSync(join(directory, 'testcases.feature'), 'utf8')
  const manifest = JSON.parse(readFileSync(join(directory, 'testcases_manifest.json'), 'utf8'))
  const validation = validateProjection(JSON.parse(modelText), featureText)
  const errors = [...validation.errors]
  const actualFiles = readdirSync(directory).sort(compareAscii)
  if (JSON.stringify(actualFiles) !== JSON.stringify([...BUNDLE_FILES].sort(compareAscii))) {
    errors.push(`bundle file set drift: ${actualFiles.join(', ')}`)
  }
  if (JSON.stringify(manifest.bundle_files) !== JSON.stringify(BUNDLE_FILES)) errors.push('manifest bundle_files drift')
  for (const record of asArray(manifest.files)) {
    const path = join(directory, record.path)
    if (!existsSync(path)) errors.push(`manifest file missing: ${record.path}`)
    else if (sha256Bytes(readFileSync(path)) !== record.sha256) errors.push(`manifest hash mismatch: ${record.path}`)
  }
  return {
    ...validation,
    status: errors.length ? 'STRUCTURE_FAIL' : 'STRUCTURE_PASS',
    errors,
  }
}
