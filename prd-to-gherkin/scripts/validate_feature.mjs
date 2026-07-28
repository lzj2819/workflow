#!/usr/bin/env node
/**
 * Deterministic delivery gate for prd-to-gherkin artifacts.
 *
 * This validator proves structural consistency only. It does not prove that the
 * PRD was interpreted completely or that two natural-language statements are
 * semantically equivalent. Those claims require an independent gold standard
 * and/or human review.
 *
 * Usage:
 *   node scripts/validate_feature.mjs <feature> <requirement-model.yaml>
 */

import { readFileSync } from 'node:fs'
import { load as loadYaml } from 'js-yaml'
import * as gherkin from '@cucumber/gherkin'
import * as messages from '@cucumber/messages'

import { containsUnresolvedUnknown } from './feature_semantic_markers.mjs'

const [featurePath, modelPath] = process.argv.slice(2)

if (!featurePath || !modelPath) {
  process.stderr.write(
    'usage: node scripts/validate_feature.mjs <feature_file> <requirement-model.yaml>\n',
  )
  process.exit(2)
}

function read(path, label) {
  try {
    return readFileSync(path, 'utf8')
  } catch (error) {
    process.stderr.write(`cannot read ${label}: ${error.message}\n`)
    process.exit(2)
  }
}

const featureRaw = read(featurePath, 'feature file')
const modelRaw = read(modelPath, 'requirement model')

function result(errors = [], details = {}) {
  return {
    status: errors.length ? 'FAIL' : 'PASS',
    errors,
    ...details,
  }
}

function uniqueIndex(items, key, label) {
  const values = new Map()
  const errors = []
  for (const [position, item] of items.entries()) {
    const id = item?.[key]
    if (typeof id !== 'string' || id.trim() === '') {
      errors.push(`${label}[${position}] has no ${key}`)
      continue
    }
    if (values.has(id)) errors.push(`duplicate ${label} ID: ${id}`)
    else values.set(id, item)
  }
  return { values, errors }
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function parseModel() {
  try {
    const model = loadYaml(modelRaw)
    if (!model || typeof model !== 'object' || Array.isArray(model)) {
      return { model: null, check: result(['YAML root must be a mapping']) }
    }
    return { model, check: result([], { parser: 'js-yaml' }) }
  } catch (error) {
    return {
      model: null,
      check: result([String(error.message ?? error)], { parser: 'js-yaml' }),
    }
  }
}

function parseGherkin() {
  try {
    const builder = new gherkin.AstBuilder(messages.IdGenerator.uuid())
    const matcher = new gherkin.GherkinClassicTokenMatcher()
    const parser = new gherkin.Parser(builder, matcher)
    parser.parse(featureRaw)
    return result([], { parser: '@cucumber/gherkin' })
  } catch (error) {
    const errors = asArray(error?.errors).length ? error.errors : [error]
    return result(
      errors.map((item) => ({
        line: item?.location?.line ?? 0,
        message: String(item?.message ?? item),
      })),
      { parser: '@cucumber/gherkin' },
    )
  }
}

function parseTableRow(line, lineNumber, errors) {
  const trimmed = line.trim()
  if (!trimmed.startsWith('|') || !trimmed.endsWith('|')) {
    errors.push(`line ${lineNumber}: Examples table row must start and end with |`)
    return []
  }
  const cells = []
  let cell = ''
  let escaped = false
  for (const character of trimmed.slice(1, -1)) {
    if (escaped) {
      cell += character === 'n' ? '\n' : character
      escaped = false
    } else if (character === '\\') {
      escaped = true
    } else if (character === '|') {
      cells.push(cell.trim())
      cell = ''
    } else {
      cell += character
    }
  }
  if (escaped) cell += '\\'
  cells.push(cell.trim())
  return cells
}

function extractScenarios() {
  const lines = featureRaw.split(/\r?\n/)
  const scenarios = []
  const errors = []
  let pendingTags = []
  let pendingScenarioId = null
  let currentScenario = null
  let currentExamples = null

  for (let index = 0; index < lines.length; index++) {
    const lineNumber = index + 1
    const line = lines[index].trim()
    const scenarioIdMatch = line.match(/^#\s*(SC-[A-Za-z0-9-]+)\b/)
    if (scenarioIdMatch) {
      if (pendingScenarioId) {
        errors.push(
          `line ${lineNumber}: ${scenarioIdMatch[1]} replaces unused ${pendingScenarioId}`,
        )
      }
      pendingScenarioId = scenarioIdMatch[1]
      continue
    }
    if (line.startsWith('@')) {
      pendingTags.push(...line.matchAll(/@([^\s@]+)/g).map((match) => match[1]))
      continue
    }
    const scenarioMatch = line.match(
      /^(Scenario Outline|Scenario Template|Scenario|Example|场景大纲|场景|剧本大纲|剧本)\s*:\s*(.+)$/,
    )
    if (scenarioMatch) {
      const keyword = scenarioMatch[1]
      currentScenario = {
        scenario_id: pendingScenarioId,
        name: scenarioMatch[2],
        line: lineNumber,
        kind: /^(?:Scenario Outline|Scenario Template|场景大纲|剧本大纲)$/.test(keyword)
          ? 'outline'
          : 'scenario',
        tags: [...pendingTags],
        steps: [],
        examples: [],
        last_phase: null,
      }
      scenarios.push(currentScenario)
      if (!pendingScenarioId) errors.push(`line ${lineNumber}: scenario has no # SC-* ID`)
      pendingTags = []
      pendingScenarioId = null
      currentExamples = null
      continue
    }
    const examplesMatch = line.match(/^(?:Examples|例子)\s*:\s*(.*)$/)
    if (examplesMatch && currentScenario) {
      currentExamples = {
        line: lineNumber,
        name: examplesMatch[1],
        header: null,
        rows: [],
      }
      currentScenario.examples.push(currentExamples)
      pendingTags = []
      continue
    }
    if (line.startsWith('|') && currentExamples) {
      const cells = parseTableRow(line, lineNumber, errors)
      if (currentExamples.header === null) {
        currentExamples.header = cells
      } else {
        currentExamples.rows.push({ line: lineNumber, cells })
      }
      continue
    }
    const stepMatch = line.match(
      /^(Given|When|Then|And|But|假如|假设|假定|当|那么|而且|并且|同时|但是)\s+(.+)$/,
    )
    if (stepMatch && currentScenario) {
      currentExamples = null
      const keyword = stepMatch[1]
      const explicitPhase =
        /^(?:Given|假如|假设|假定)$/.test(keyword)
          ? 'given'
          : /^(?:When|当)$/.test(keyword)
            ? 'when'
            : /^(?:Then|那么)$/.test(keyword)
              ? 'then'
              : null
      const phase = explicitPhase ?? currentScenario.last_phase
      currentScenario.steps.push({ phase, text: stepMatch[2] })
      if (phase) currentScenario.last_phase = phase
      continue
    }
    if (
      line &&
      !line.startsWith('#') &&
      !/^(?:Feature|Rule|Background|Examples|功能|规则|背景|例子)\s*:/.test(line)
    ) {
      currentExamples = null
      // Tags and IDs must be immediately associated with a scenario header.
      if (!/^(?:Given|When|Then|And|But|\*|假如|假设|假定|当|那么|而且|并且|同时|但是)\b/.test(line)
        && !line.startsWith('|')) {
        pendingTags = []
        pendingScenarioId = null
      }
    }
  }
  if (pendingScenarioId) errors.push(`unused scenario ID at end of file: ${pendingScenarioId}`)
  return { scenarios, errors }
}

function rootRequirementId(requirementId) {
  const match = String(requirementId ?? '').match(/^((?:REQ|NFR|MET)-[^-]+)-R\d+$/)
  return match?.[1] ?? null
}

function tcStepTemplate(tc) {
  if (tc?.step_template && typeof tc.step_template === 'object') {
    return tc.step_template
  }
  return {
    precondition: tc?.precondition,
    action: tc?.action,
    expected: tc?.expected,
  }
}

function placeholdersIn(template) {
  const names = []
  const seen = new Set()
  for (const field of ['precondition', 'action', 'expected']) {
    for (const match of String(template?.[field] ?? '').matchAll(/<([^<>]+)>/g)) {
      if (!seen.has(match[1])) {
        seen.add(match[1])
        names.push(match[1])
      }
    }
  }
  return names
}

function sameStringArray(left, right) {
  return (
    left.length === right.length &&
    left.every((value, index) => value === right[index])
  )
}

function validateModel(model) {
  const errors = []
  const groups = asArray(model.requirement_groups)
  const facts = groups.flatMap((group) => asArray(group?.clauses))
  const ir = asArray(model.requirement_ir)
  const derivations = asArray(model.derivations)
  const acs = asArray(model.acceptance_criteria)
  const tcs = asArray(model.test_conditions)
  const compositions = asArray(model.scenario_compositions)
  const decisions = asArray(model.open_decisions)
  const eligibleRequirementIds = new Set(asArray(model?.baseline?.eligible_requirement_ids))

  const factIndex = uniqueIndex(facts, 'fact_id', 'FACT')
  const irIndex = uniqueIndex(ir, 'requirement_id', 'Requirement IR')
  const drIndex = uniqueIndex(derivations, 'derived_id', 'derivation')
  const acIndex = uniqueIndex(acs, 'ac_id', 'acceptance criterion')
  const tcIndex = uniqueIndex(tcs, 'tc_id', 'test condition')
  const compositionIndex = uniqueIndex(compositions, 'composition_id', 'scenario composition')
  errors.push(
    ...factIndex.errors,
    ...irIndex.errors,
    ...drIndex.errors,
    ...acIndex.errors,
    ...tcIndex.errors,
    ...compositionIndex.errors,
  )

  if (model?.baseline?.status !== 'FROZEN') {
    errors.push(`baseline.status must be FROZEN, got ${String(model?.baseline?.status)}`)
  }

  for (const decision of decisions) {
    if (
      decision?.classification === 'BLOCKING' &&
      !['ACCEPTED', 'REJECTED', 'BASELINED'].includes(decision?.status) &&
      asArray(decision?.affected_requirements).some((id) => eligibleRequirementIds.has(id))
    ) {
      errors.push(
        `unresolved BLOCKING open decision affects eligible requirements: ` +
          `${decision?.id ?? '<missing id>'}`,
      )
    }
  }

  const allowedEvidence = new Set([...factIndex.values.keys(), ...drIndex.values.keys()])
  for (const derivation of derivations) {
    if (derivation?.decision === 'VALID_DERIVATION') {
      for (const premise of asArray(derivation.premises)) {
        if (!factIndex.values.has(premise?.fact_id)) {
          errors.push(`${derivation.derived_id} references missing FACT ${premise?.fact_id}`)
        }
      }
    }
  }

  for (const ac of acs) {
    if (!irIndex.values.has(ac.requirement_id)) {
      errors.push(`${ac.ac_id} references missing Requirement IR ${ac.requirement_id}`)
    }
    if (!ac?.oracle?.type || !ac?.oracle?.expected) {
      errors.push(`${ac.ac_id} has no deterministic oracle type/expected value`)
    }
    for (const evidence of asArray(ac.evidence)) {
      if (!allowedEvidence.has(evidence)) {
        errors.push(`${ac.ac_id} references missing evidence ${evidence}`)
      }
    }
  }

  for (const requirement of ir) {
    if (
      requirement.requirement_kind !== undefined &&
      !['atomic', 'aggregate'].includes(requirement.requirement_kind)
    ) {
      errors.push(
        `${requirement.requirement_id} has invalid requirement_kind ${requirement.requirement_kind}`,
      )
    }
    if (requirement.requirement_kind === 'aggregate') {
      const children = asArray(requirement.covered_by_requirements)
      if (!children.length) {
        errors.push(`${requirement.requirement_id} is aggregate but has no covered children`)
      }
      for (const childId of children) {
        if (!irIndex.values.has(childId)) {
          errors.push(`${requirement.requirement_id} covers missing child IR ${childId}`)
        } else if (childId === requirement.requirement_id) {
          errors.push(`${requirement.requirement_id} cannot cover itself`)
        }
      }
    }
  }

  for (const tc of tcs) {
    if (!irIndex.values.has(tc.requirement_id)) {
      errors.push(`${tc.tc_id} references missing Requirement IR ${tc.requirement_id}`)
    }
    if (!tc.step_template || typeof tc.step_template !== 'object') {
      errors.push(`${tc.tc_id} must define step_template`)
    }
    if (tc.render_mode === undefined) {
      errors.push(`${tc.tc_id} must define render_mode`)
    }
    const template = tcStepTemplate(tc)
    if (!template.precondition || !template.action || !template.expected) {
      errors.push(
        `${tc.tc_id} must define step_template precondition, action, and expected`,
      )
    }
    if (
      tc.render_mode !== undefined &&
      !['SCENARIO', 'SCENARIO_OUTLINE'].includes(tc.render_mode)
    ) {
      errors.push(`${tc.tc_id} has invalid render_mode ${String(tc.render_mode)}`)
    }
    if (tc.render_mode !== undefined) {
      const columns = asArray(tc.example_columns)
      const rows = asArray(tc.approved_data_rows)
      const placeholders = placeholdersIn(template)
      const duplicateColumns = columns.filter(
        (column, index) => columns.indexOf(column) !== index,
      )
      if (duplicateColumns.length) {
        errors.push(`${tc.tc_id} has duplicate example_columns: ${duplicateColumns.join(', ')}`)
      }
      if (tc.render_mode === 'SCENARIO') {
        if (columns.length || rows.length || placeholders.length) {
          errors.push(
            `${tc.tc_id} SCENARIO must not define example columns, data rows, or placeholders`,
          )
        }
      } else if (tc.render_mode === 'SCENARIO_OUTLINE') {
        if (!columns.length || !rows.length) {
          errors.push(`${tc.tc_id} SCENARIO_OUTLINE requires columns and approved data rows`)
        }
        if (!sameStringArray(placeholders, columns)) {
          errors.push(
            `${tc.tc_id} placeholders [${placeholders.join(', ')}] do not match ` +
              `example_columns [${columns.join(', ')}]`,
          )
        }
        const rowIds = new Set()
        for (const [rowIndex, row] of rows.entries()) {
          const rowLabel = `${tc.tc_id}.approved_data_rows[${rowIndex}]`
          if (!row || typeof row !== 'object' || Array.isArray(row)) {
            errors.push(`${rowLabel} must be a mapping`)
            continue
          }
          if (typeof row.row_id !== 'string' || !row.row_id.trim()) {
            errors.push(`${rowLabel} has no row_id`)
          } else if (rowIds.has(row.row_id)) {
            errors.push(`${tc.tc_id} has duplicate row_id ${row.row_id}`)
          } else {
            rowIds.add(row.row_id)
          }
          const values =
            row.values && typeof row.values === 'object' && !Array.isArray(row.values)
              ? row.values
              : null
          if (!values) {
            errors.push(`${rowLabel} values must be a mapping`)
          } else {
            const valueColumns = Object.keys(values)
            if (!sameStringArray(valueColumns, columns)) {
              errors.push(
                `${rowLabel} value columns [${valueColumns.join(', ')}] do not match ` +
                  `[${columns.join(', ')}]`,
              )
            }
            for (const column of columns) {
              if (
                values[column] === undefined ||
                values[column] === null ||
                String(values[column]) === ''
              ) {
                errors.push(`${rowLabel} has empty value for ${column}`)
              }
            }
          }
          if (!asArray(row.evidence).length) {
            errors.push(`${rowLabel} has no evidence`)
          }
          for (const evidence of asArray(row.evidence)) {
            if (!allowedEvidence.has(evidence)) {
              errors.push(`${rowLabel} references missing evidence ${evidence}`)
            }
          }
        }
      }
    }
    for (const requirementId of asArray(tc.covered_requirement_ids)) {
      if (!irIndex.values.has(requirementId)) {
        errors.push(`${tc.tc_id} covers missing Requirement IR ${requirementId}`)
      }
    }
    for (const acId of asArray(tc.acceptance_criteria)) {
      const ac = acIndex.values.get(acId)
      if (!ac) errors.push(`${tc.tc_id} references missing AC ${acId}`)
      else if (ac.requirement_id !== tc.requirement_id) {
        errors.push(
          `${tc.tc_id} and ${acId} disagree on requirement_id ` +
            `(${tc.requirement_id} vs ${ac.requirement_id})`,
        )
      }
    }
    for (const evidence of asArray(tc.evidence)) {
      if (!allowedEvidence.has(evidence)) {
        errors.push(`${tc.tc_id} references missing evidence ${evidence}`)
      } else if (
        evidence.startsWith('DR-') &&
        drIndex.values.get(evidence)?.decision !== 'VALID_DERIVATION'
      ) {
        errors.push(`${tc.tc_id} uses non-valid derivation ${evidence}`)
      }
    }
  }

  for (const composition of compositions) {
    if (composition?.status !== 'VALID_COMPOSITION') continue
    if (asArray(composition.component_tc_ids).length < 2) {
      errors.push(`${composition.composition_id} has fewer than two component TCs`)
    }
    for (const tcId of asArray(composition.component_tc_ids)) {
      if (!tcIndex.values.has(tcId)) {
        errors.push(`${composition.composition_id} references missing TC ${tcId}`)
      }
    }
    for (const transition of asArray(composition.ordered_transitions)) {
      if (!asArray(transition?.bridge?.evidence).length) {
        errors.push(`${composition.composition_id} has an evidence-free bridge`)
      }
    }
  }

  const expandEvidenceToFacts = (evidenceIds) => {
    const covered = new Set()
    for (const evidence of evidenceIds) {
      if (factIndex.values.has(evidence)) covered.add(evidence)
      const derivation = drIndex.values.get(evidence)
      if (derivation?.decision === 'VALID_DERIVATION') {
        for (const premise of asArray(derivation.premises)) {
          if (factIndex.values.has(premise?.fact_id)) covered.add(premise.fact_id)
        }
      }
    }
    return covered
  }
  const acEvidence = acs.flatMap((ac) => asArray(ac.evidence))
  const tcEvidence = tcs.flatMap((tc) => asArray(tc.evidence))
  const factsCoveredByAc = expandEvidenceToFacts(acEvidence)
  const factsCoveredByTc = expandEvidenceToFacts(tcEvidence)
  const requirementsCoveredByAc = new Set(acs.map((ac) => ac.requirement_id))
  const requirementsCoveredByTc = new Set()
  for (const tc of tcs) {
    requirementsCoveredByTc.add(tc.requirement_id)
    for (const requirementId of asArray(tc.covered_requirement_ids)) {
      requirementsCoveredByTc.add(requirementId)
    }
    for (const acId of asArray(tc.acceptance_criteria)) {
      const acRequirementId = acIndex.values.get(acId)?.requirement_id
      if (acRequirementId) requirementsCoveredByTc.add(acRequirementId)
    }
  }
  const acsCoveredByTc = new Set(tcs.flatMap((tc) => asArray(tc.acceptance_criteria)))

  const authoritativeFacts = facts.filter((fact) => fact?.status === 'EXPLICIT')
  const sourceBackedRequirements = ir.filter((requirement) => requirement?.status === 'SOURCE_BACKED')
  const atomicRequirements = sourceBackedRequirements.filter(
    (requirement) => requirement?.requirement_kind !== 'aggregate',
  )
  const aggregateRequirements = sourceBackedRequirements.filter(
    (requirement) => requirement?.requirement_kind === 'aggregate',
  )
  const aggregateCoveredBy = (coverageSet, requirement) =>
    asArray(requirement.covered_by_requirements).length > 0 &&
    asArray(requirement.covered_by_requirements).every((id) => coverageSet.has(id))
  for (const requirement of aggregateRequirements) {
    if (aggregateCoveredBy(requirementsCoveredByAc, requirement)) {
      requirementsCoveredByAc.add(requirement.requirement_id)
    }
    if (aggregateCoveredBy(requirementsCoveredByTc, requirement)) {
      requirementsCoveredByTc.add(requirement.requirement_id)
    }
  }

  const dispositions = asArray(model.ir_dispositions)
  if (model.ir_dispositions !== undefined) {
    const dispositionIndex = uniqueIndex(dispositions, 'requirement_id', 'IR disposition')
    errors.push(...dispositionIndex.errors)
    const allowedDispositions = new Set([
      'AC_CREATED',
      'AGGREGATE_COVERED_BY',
      'BLOCKED_NO_ORACLE',
      'BLOCKED_BY_GAP',
      'DOCUMENTED_EXCLUSION',
    ])
    for (const disposition of dispositions) {
      const requirement = irIndex.values.get(disposition.requirement_id)
      if (!requirement) {
        errors.push(`IR disposition references missing IR ${disposition.requirement_id}`)
        continue
      }
      if (!allowedDispositions.has(disposition.disposition)) {
        errors.push(
          `${disposition.requirement_id} has invalid disposition ${disposition.disposition}`,
        )
      }
      if (
        disposition.disposition === 'AC_CREATED' &&
        !asArray(disposition.ac_ids).length
      ) {
        errors.push(`${disposition.requirement_id} AC_CREATED has no ac_ids`)
      }
      if (
        disposition.disposition === 'AGGREGATE_COVERED_BY' &&
        requirement.requirement_kind !== 'aggregate'
      ) {
        errors.push(
          `${disposition.requirement_id} uses AGGREGATE_COVERED_BY but is not aggregate`,
        )
      }
    }
    for (const requirementId of irIndex.values.keys()) {
      if (!dispositionIndex.values.has(requirementId)) {
        errors.push(`${requirementId} has no IR disposition`)
      }
    }
  }

  const eligibleRequirements = sourceBackedRequirements.filter((requirement) =>
    eligibleRequirementIds.has(requirement.requirement_id),
  )
  const eligibleGroupIds = new Set(
    eligibleRequirements.map((requirement) => requirement.requirement_group),
  )
  const eligibleFacts = groups
    .filter((group) => eligibleGroupIds.has(group.requirement_group_id))
    .flatMap((group) => asArray(group?.clauses))
    .filter((fact) => fact?.status === 'EXPLICIT')
  const eligibleAtomicRequirements = atomicRequirements.filter((requirement) =>
    eligibleRequirementIds.has(requirement.requirement_id),
  )
  const eligibleAggregateRequirements = aggregateRequirements.filter((requirement) =>
    eligibleRequirementIds.has(requirement.requirement_id),
  )

  const coverageGaps = {
    facts_without_ac: eligibleFacts
      .map((fact) => fact.fact_id)
      .filter((id) => !factsCoveredByAc.has(id)),
    facts_without_tc: eligibleFacts
      .map((fact) => fact.fact_id)
      .filter((id) => !factsCoveredByTc.has(id)),
    requirements_without_ac: eligibleAtomicRequirements
      .map((requirement) => requirement.requirement_id)
      .filter((id) => !requirementsCoveredByAc.has(id)),
    requirements_without_tc: eligibleAtomicRequirements
      .map((requirement) => requirement.requirement_id)
      .filter((id) => !requirementsCoveredByTc.has(id)),
    unresolved_aggregate_requirements: eligibleAggregateRequirements
      .map((requirement) => requirement.requirement_id)
      .filter(
        (id) =>
          !requirementsCoveredByAc.has(id) ||
          !requirementsCoveredByTc.has(id),
      ),
    acs_without_tc: acs.map((ac) => ac.ac_id).filter((id) => !acsCoveredByTc.has(id)),
  }
  for (const [dimension, ids] of Object.entries(coverageGaps)) {
    if (ids.length) errors.push(`${dimension}: ${ids.join(', ')}`)
  }

  const actual = {
    facts: authoritativeFacts.length,
    requirements: sourceBackedRequirements.length,
    acceptance_criteria: acs.length,
    test_conditions: tcs.length,
  }
  const declared = model.coverage ?? {}
  const declaredPairs = [
    ['facts.total', declared?.facts?.total, actual.facts],
    ['requirements.total', declared?.requirements?.total, actual.requirements],
    ['acceptance_criteria.total', declared?.acceptance_criteria?.total, actual.acceptance_criteria],
    ['test_conditions.total', declared?.test_conditions?.total, actual.test_conditions],
  ]
  for (const [field, reported, count] of declaredPairs) {
    if (reported !== undefined && reported !== count) {
      errors.push(`coverage.${field} declares ${reported}, but the model contains ${count}`)
    }
  }

  return {
    check: result(errors, {
      counts: actual,
      coverage_gaps: coverageGaps,
      unresolved_blocking_decisions: decisions.filter(
        (item) =>
          item?.classification === 'BLOCKING' &&
          !['ACCEPTED', 'REJECTED', 'BASELINED'].includes(item?.status) &&
          asArray(item?.affected_requirements).some((id) =>
            eligibleRequirementIds.has(id),
          ),
      ).length,
    }),
    indexes: { factIndex, irIndex, drIndex, acIndex, tcIndex, compositionIndex },
  }
}

function validateTraceability(modelValidation) {
  const errors = [...scenarioExtraction.errors]
  const scenarioIds = new Set()
  const renderedTcs = new Map()
  const renderedCompositions = new Map()
  const knownTcs = modelValidation.indexes.tcIndex.values
  const knownCompositions = modelValidation.indexes.compositionIndex.values
  const normalizeStep = (value) => String(value ?? '').replace(/\s+/g, ' ').trim()
  let approvedExampleRows = 0
  let matchedExampleRows = 0

  if (/^\s*#\s*language\s*:/mu.test(featureRaw)) {
    errors.push('language directive is forbidden; use canonical English Gherkin keywords')
  }
  if (
    /^\s*(?:功能|场景|场景大纲|假如|假设|假定|当|那么|而且|并且|同时|但是)\s*[: ]/mu.test(
      featureRaw,
    )
  ) {
    errors.push('localized Gherkin keyword found; use Feature/Scenario/Given/When/Then/And/But')
  }

  for (const scenario of scenarioExtraction.scenarios) {
    if (scenario.scenario_id) {
      if (scenarioIds.has(scenario.scenario_id)) {
        errors.push(`duplicate Scenario ID: ${scenario.scenario_id}`)
      }
      scenarioIds.add(scenario.scenario_id)
    }

    const tcTags = scenario.tags.filter((tag) => tag.startsWith('TC-'))
    const compositionTags = scenario.tags.filter((tag) => tag.startsWith('COMP-'))
    if (compositionTags.length) {
      if (compositionTags.length !== 1 || tcTags.length !== 0) {
        errors.push(
          `${scenario.scenario_id ?? `line ${scenario.line}`} must have one @COMP-* ` +
            `and no @TC-* tags`,
        )
        continue
      }
      const compositionId = compositionTags[0]
      const composition = knownCompositions.get(compositionId)
      if (!composition || composition.status !== 'VALID_COMPOSITION') {
        errors.push(`${scenario.scenario_id} references unknown or invalid ${compositionId}`)
        continue
      }
      if (scenario.kind === 'outline' || scenario.examples.length) {
        errors.push(`${scenario.scenario_id} composition must use Scenario without Examples`)
      }
      if (renderedCompositions.has(compositionId)) {
        errors.push(`${compositionId} is rendered by more than one scenario`)
      } else {
        renderedCompositions.set(compositionId, scenario.scenario_id)
      }
      const coveredRequirementIds = new Set()
      for (const tcId of asArray(composition.component_tc_ids)) {
        const tc = knownTcs.get(tcId)
        if (!tc) continue
        coveredRequirementIds.add(tc.requirement_id)
        for (const requirementId of asArray(tc.covered_requirement_ids)) {
          coveredRequirementIds.add(requirementId)
        }
      }
      for (const requirementId of coveredRequirementIds) {
        const requirementTag = rootRequirementId(requirementId)
        if (requirementTag && !scenario.tags.includes(requirementTag)) {
          errors.push(
            `${scenario.scenario_id} is missing @${requirementTag} required by ${compositionId}`,
          )
        }
      }
      continue
    }
    if (tcTags.length !== 1) {
      errors.push(
        `${scenario.scenario_id ?? `line ${scenario.line}`} must have exactly one @TC-* tag`,
      )
      continue
    }

    const tcId = tcTags[0]
    const tc = knownTcs.get(tcId)
    if (!tc) {
      errors.push(`${scenario.scenario_id} references unknown TC ${tcId}`)
      continue
    }
    if (renderedTcs.has(tcId)) {
      errors.push(`${tcId} is rendered by more than one scenario`)
    } else {
      renderedTcs.set(tcId, scenario.scenario_id)
    }

    const template = tcStepTemplate(tc)
    const modelRows = asArray(tc.approved_data_rows)
    if (tc.render_mode === 'SCENARIO') {
      if (scenario.kind !== 'scenario' || scenario.examples.length) {
        errors.push(`${scenario.scenario_id} must render ${tcId} as Scenario without Examples`)
      }
    } else if (tc.render_mode === 'SCENARIO_OUTLINE') {
      approvedExampleRows += modelRows.length
      if (scenario.kind !== 'outline') {
        errors.push(`${scenario.scenario_id} must render ${tcId} as Scenario Outline`)
      }
      if (scenario.examples.length !== 1) {
        errors.push(
          `${scenario.scenario_id} must contain exactly one Examples block, got ` +
            `${scenario.examples.length}`,
        )
      } else {
        const examples = scenario.examples[0]
        const header = examples.header ?? []
        const columns = asArray(tc.example_columns)
        if (!sameStringArray(header, columns)) {
          errors.push(
            `${scenario.scenario_id} Examples header [${header.join(', ')}] does not match ` +
              `[${columns.join(', ')}]`,
          )
        }
        if (examples.rows.length !== modelRows.length) {
          errors.push(
            `${scenario.scenario_id} Examples has ${examples.rows.length} rows; ` +
              `${tcId} approves ${modelRows.length}`,
          )
        }
        const comparedRows = Math.min(examples.rows.length, modelRows.length)
        for (let rowIndex = 0; rowIndex < comparedRows; rowIndex++) {
          const renderedRow = examples.rows[rowIndex]
          const modelValues = modelRows[rowIndex]?.values
          const expectedCells = columns.map((column) => String(modelValues?.[column] ?? ''))
          if (!sameStringArray(renderedRow.cells, expectedCells)) {
            errors.push(
              `${scenario.scenario_id} Examples row ${rowIndex + 1} ` +
                `[${renderedRow.cells.join(', ')}] does not match ` +
                `${modelRows[rowIndex]?.row_id ?? `model row ${rowIndex + 1}`} ` +
                `[${expectedCells.join(', ')}]`,
            )
          } else {
            matchedExampleRows++
          }
        }
        for (const row of examples.rows) {
          if (row.cells.length !== header.length) {
            errors.push(
              `${scenario.scenario_id} Examples line ${row.line} has ${row.cells.length} ` +
                `cells; header has ${header.length}`,
            )
          }
        }
      }
    } else if (scenario.kind === 'outline' || scenario.examples.length) {
      errors.push(
        `${scenario.scenario_id} uses Outline/Examples but ${tcId} has no render_mode contract`,
      )
    }

    const renderedFields = {
      precondition: scenario.steps
        .filter((step) => step.phase === 'given')
        .map((step) => step.text)
        .join('；'),
      action: scenario.steps
        .filter((step) => step.phase === 'when')
        .map((step) => step.text)
        .join('；'),
      expected: scenario.steps
        .filter((step) => step.phase === 'then')
        .map((step) => step.text)
        .join('；'),
    }
    for (const [field, rendered] of Object.entries(renderedFields)) {
      if (normalizeStep(rendered) !== normalizeStep(template[field])) {
        errors.push(
          `${scenario.scenario_id} ${field} drifts from ${tcId}: ` +
            `"${rendered}" vs "${String(template[field] ?? '')}"`,
        )
      }
    }

    const coveredRequirementIds = new Set([
      tc.requirement_id,
      ...asArray(tc.covered_requirement_ids),
      ...asArray(tc.acceptance_criteria)
        .map((acId) => modelValidation.indexes.acIndex.values.get(acId)?.requirement_id)
        .filter(Boolean),
    ])
    for (const requirementId of coveredRequirementIds) {
      const requirementTag = rootRequirementId(requirementId)
      if (!requirementTag) {
        errors.push(`${tcId} has an invalid covered requirement_id: ${requirementId}`)
      } else if (!scenario.tags.includes(requirementTag)) {
        errors.push(
          `${scenario.scenario_id} is missing @${requirementTag} required by ${tcId}`,
        )
      }
    }
  }

  for (const tcId of knownTcs.keys()) {
    if (!renderedTcs.has(tcId)) errors.push(`${tcId} is not rendered to any Scenario`)
  }
  for (const [compositionId, composition] of knownCompositions) {
    if (
      composition.status === 'VALID_COMPOSITION' &&
      !renderedCompositions.has(compositionId)
    ) {
      errors.push(`${compositionId} is not rendered to any Scenario`)
    }
  }

  if (/\bHYP-[A-Za-z0-9-]+\b/.test(featureRaw)) {
    errors.push('HYPOTHESIS identifier leaked into the authoritative feature')
  }
  if (containsUnresolvedUnknown(featureRaw)) {
    errors.push('UNKNOWN content leaked into the authoritative feature')
  }

  return result(errors, {
    scenarios: scenarioExtraction.scenarios.length,
    unique_scenario_ids: scenarioIds.size,
    rendered_test_conditions: renderedTcs.size,
    rendered_compositions: renderedCompositions.size,
    approved_example_rows: approvedExampleRows,
    matched_example_rows: matchedExampleRows,
    approved_example_row_coverage:
      approvedExampleRows === 0 ? 1 : matchedExampleRows / approvedExampleRows,
  })
}

const modelParse = parseModel()
const syntax = parseGherkin()
const scenarioExtraction = extractScenarios()
const modelValidation = modelParse.model
  ? validateModel(modelParse.model)
  : {
      check: result(['model validation skipped because YAML parsing failed']),
      indexes: {
        factIndex: { values: new Map() },
        irIndex: { values: new Map() },
        drIndex: { values: new Map() },
        acIndex: { values: new Map() },
        tcIndex: { values: new Map() },
        compositionIndex: { values: new Map() },
      },
    }
const traceability = modelParse.model
  ? validateTraceability(modelValidation)
  : result(['traceability validation skipped because YAML parsing failed'])

const checks = {
  gherkin_syntax: syntax,
  model_yaml: modelParse.check,
  model_integrity: modelValidation.check,
  tc_to_scenario_traceability: traceability,
}
const failedChecks = Object.entries(checks)
  .filter(([, check]) => check.status === 'FAIL')
  .map(([name]) => name)

const output = {
  validator_scope: {
    proves: [
      'Gherkin syntax',
      'YAML parseability and ID uniqueness',
      'baseline and unresolved BLOCKING decision gates',
      'FACT/DR/IR/AC/TC reference integrity',
      'declared model counts match actual objects',
      'atomic Scenarios map to one TC; composition Scenarios map to one valid composition',
      'all model TCs and valid compositions are rendered exactly once',
      'Scenario and Scenario Outline steps match TC step templates after whitespace normalization',
      'Outline placeholders, Examples headers, row order, and values match approved model data',
      'approved Examples row coverage',
      'Feature uses canonical English Gherkin keywords and no language directive',
      'no literal HYP-* or unresolved UNKNOWN marker leaks into the feature',
    ],
    does_not_prove: [
      'complete interpretation of the source PRD',
      'natural-language semantic equivalence of Then and AC oracle',
      'absence of all unsupported business semantics',
      'minimality or non-redundancy of the test set',
    ],
  },
  feature_file: featurePath,
  requirement_model: modelPath,
  checks,
  failed_checks: failedChecks,
  deterministic_gate: failedChecks.length ? 'FAIL' : 'PASS',
}

process.stdout.write(`${JSON.stringify(output, null, 2)}\n`)
process.exit(failedChecks.length ? 1 : 0)
