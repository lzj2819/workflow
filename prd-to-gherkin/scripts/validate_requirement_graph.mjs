#!/usr/bin/env node
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { load as loadYaml } from 'js-yaml'

const here = dirname(fileURLToPath(import.meta.url))
const defaultOntologyPath = resolve(here, '../references/requirement-ontology.yaml')
const defaultPatternLibraryPath = resolve(here, '../references/requirement-patterns.yaml')
const defaultCoverageSchemaPath = resolve(here, '../references/coverage-graph-schema.yaml')

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function parseYaml(path) {
  return loadYaml(readFileSync(path, 'utf8'))
}

function indexBy(items, key, label, errors) {
  const index = new Map()
  for (const [position, item] of items.entries()) {
    const id = item?.[key]
    if (typeof id !== 'string' || id === '') {
      errors.push(`${label}[${position}] has no ${key}`)
    } else if (index.has(id)) {
      errors.push(`duplicate ${label} ${id}`)
    } else {
      index.set(id, item)
    }
  }
  return index
}

function endpointAllowed(allowed, actual) {
  return asArray(allowed).includes('*') || asArray(allowed).includes(actual)
}

function validateTypedGraph(graph, ontology, errors) {
  const nodes = asArray(graph?.nodes)
  const edges = asArray(graph?.edges)
  const nodeIndex = indexBy(nodes, 'node_id', 'semantic node', errors)
  indexBy(edges, 'edge_id', 'semantic edge', errors)

  for (const node of nodes) {
    const contract = ontology.node_types?.[node.type]
    const isCore = Boolean(contract)
    const isNamespacedExtension =
      typeof node.type === 'string' && /^[a-z][a-z0-9-]*:[A-Za-z][A-Za-z0-9]*$/.test(node.type)
    if (!isCore && !isNamespacedExtension) {
      errors.push(`${node.node_id} has unknown ontology type ${String(node.type)}`)
    }
    if (!node.label) errors.push(`${node.node_id} has no label`)
    for (const property of asArray(contract?.required_properties)) {
      if (node?.properties?.[property] === undefined) {
        errors.push(`${node.node_id} lacks required property ${property}`)
      }
    }
    if (!asArray(node.evidence).length) {
      errors.push(`${node.node_id} has no evidence`)
    } else if (
      asArray(node.evidence).some(
        (item) => !item?.fact_id || !item?.source_ref,
      )
    ) {
      errors.push(`${node.node_id} has malformed evidence`)
    }
  }

  for (const edge of edges) {
    const contract = ontology.edge_types?.[edge.type]
    const from = nodeIndex.get(edge.from)
    const to = nodeIndex.get(edge.to)
    if (!contract) errors.push(`${edge.edge_id} has unknown ontology edge type ${edge.type}`)
    if (!from) errors.push(`${edge.edge_id} has missing from node ${edge.from}`)
    if (!to) errors.push(`${edge.edge_id} has missing to node ${edge.to}`)
    if (contract && from && !endpointAllowed(contract.from, from.type)) {
      errors.push(`${edge.edge_id} rejects from type ${from.type}`)
    }
    if (contract && to && !endpointAllowed(contract.to, to.type)) {
      errors.push(`${edge.edge_id} rejects to type ${to.type}`)
    }
    if (!asArray(edge.evidence).length) {
      errors.push(`${edge.edge_id} has no evidence`)
    } else if (
      asArray(edge.evidence).some(
        (item) => !item?.fact_id || !item?.source_ref,
      )
    ) {
      errors.push(`${edge.edge_id} has malformed evidence`)
    }
  }
}

function validatePatternCandidates(candidates, patternLibrary, errors) {
  const allowed = new Set(['DETECTED', 'VALIDATED', 'REJECTED', 'AMBIGUOUS'])
  const knownPatterns = new Set(asArray(patternLibrary?.rules).map((rule) => rule.pattern_id))
  indexBy(asArray(candidates), 'candidate_id', 'pattern candidate', errors)
  for (const candidate of asArray(candidates)) {
    if (
      !candidate.pattern_id ||
      !candidate.source_ref ||
      !candidate.matched_text ||
      candidate.proposed_structure === undefined
    ) {
      errors.push(`${candidate.candidate_id} lacks pattern provenance`)
    }
    if (!knownPatterns.has(candidate.pattern_id)) {
      errors.push(`${candidate.candidate_id} references unknown pattern ${candidate.pattern_id}`)
    }
    if (!allowed.has(candidate.status)) {
      errors.push(`${candidate.candidate_id} has invalid status ${String(candidate.status)}`)
    }
    if (candidate.status === 'DETECTED') {
      errors.push(`${candidate.candidate_id} has no final disposition`)
    }
  }
}

function reachable(adjacency, start, target) {
  const pending = [start]
  const seen = new Set()
  while (pending.length) {
    const node = pending.pop()
    if (node === target) return true
    if (seen.has(node)) continue
    seen.add(node)
    pending.push(...(adjacency.get(node) ?? []))
  }
  return false
}

function reachesType(adjacency, nodeIndex, start, targetTypes) {
  const pending = [start]
  const seen = new Set()
  while (pending.length) {
    const nodeId = pending.pop()
    if (seen.has(nodeId)) continue
    seen.add(nodeId)
    if (targetTypes.has(nodeIndex.get(nodeId)?.type)) return true
    pending.push(...(adjacency.get(nodeId) ?? []))
  }
  return false
}

function ratio(covered, total) {
  return total === 0 ? 1 : covered / total
}

function validateCoverageGraph(graph, schema, errors) {
  const nodes = asArray(graph?.nodes)
  const edges = asArray(graph?.edges)
  const nodeIndex = indexBy(nodes, 'node_id', 'coverage node', errors)
  indexBy(edges, 'edge_id', 'coverage edge', errors)
  const knownNodeTypes = new Set(asArray(schema.node_types))
  const adjacency = new Map()

  for (const node of nodes) {
    if (!knownNodeTypes.has(node.type)) {
      errors.push(`${node.node_id} has unknown coverage node type ${node.type}`)
    }
  }

  for (const edge of edges) {
    const contract = schema.edge_types?.[edge.type]
    const from = nodeIndex.get(edge.from)
    const to = nodeIndex.get(edge.to)
    if (!contract) errors.push(`${edge.edge_id} has unknown coverage edge type ${edge.type}`)
    if (!from) errors.push(`${edge.edge_id} has missing from node ${edge.from}`)
    if (!to) errors.push(`${edge.edge_id} has missing to node ${edge.to}`)
    if (contract && from && !endpointAllowed(contract.from, from.type)) {
      errors.push(`${edge.edge_id} rejects from type ${from.type}`)
    }
    if (contract && to && !endpointAllowed(contract.to, to.type)) {
      errors.push(`${edge.edge_id} rejects to type ${to.type}`)
    }
    if (from && to) {
      if (!adjacency.has(from.node_id)) adjacency.set(from.node_id, [])
      adjacency.get(from.node_id).push(to.node_id)
    }
  }

  const sourceIds = nodes.filter((node) => node.type === 'SOURCE').map((node) => node.node_id)
  const scenarioIds = nodes
    .filter((node) => node.type === 'SCENARIO' && node.status === 'AUTHORITATIVE')
    .map((node) => node.node_id)
  for (const scenarioId of scenarioIds) {
    if (!sourceIds.some((sourceId) => reachable(adjacency, sourceId, scenarioId))) {
      errors.push(`${scenarioId} has no authoritative path from SOURCE`)
    }
  }

  const tcIds = nodes
    .filter((node) => node.type === 'TEST_CONDITION' && node.status === 'FROZEN')
    .map((node) => node.node_id)
  for (const tcId of tcIds) {
    const renderCount = edges.filter(
      (edge) => edge.type === 'RENDERED_AS' && edge.from === tcId,
    ).length
    if (renderCount !== 1) errors.push(`${tcId} has ${renderCount} RENDERED_AS edges`)
  }

  const sourceClauses = nodes.filter(
    (node) => node.type === 'CLAUSE' && node.status === 'AUTHORITATIVE',
  )
  const eligibleFacts = nodes.filter(
    (node) =>
      node.type === 'FACT' && !['BLOCKED', 'EXCLUDED', 'INVALID'].includes(node.status),
  )
  const eligibleRequirements = nodes.filter(
    (node) => node.type === 'REQUIREMENT_IR' && node.status === 'ELIGIBLE',
  )
  const authoritativeObligations = nodes.filter(
    (node) => node.type === 'TEST_OBLIGATION' && node.status === 'AUTHORITATIVE',
  )
  const countReachable = (items, types) =>
    items.filter((node) => reachesType(adjacency, nodeIndex, node.node_id, new Set(types))).length
  const sourceAccounted = countReachable(sourceClauses, ['FACT', 'EXCLUSION'])
  const factsCovered = countReachable(eligibleFacts, ['TEST_CONDITION'])
  const requirementsCovered = countReachable(eligibleRequirements, ['TEST_CONDITION'])
  const obligationsCovered = countReachable(authoritativeObligations, ['TEST_CONDITION'])
  const tcsRendered = countReachable(
    nodes.filter((node) => node.type === 'TEST_CONDITION' && node.status === 'FROZEN'),
    ['SCENARIO'],
  )

  return {
    nodes: nodes.length,
    edges: edges.length,
    authoritative_scenarios: scenarioIds.length,
    frozen_test_conditions: tcIds.length,
    coverage: {
      source_accounting_rate: ratio(sourceAccounted, sourceClauses.length),
      eligible_fact_test_coverage: ratio(factsCovered, eligibleFacts.length),
      eligible_ir_test_coverage: ratio(requirementsCovered, eligibleRequirements.length),
      test_obligation_tc_coverage: ratio(
        obligationsCovered,
        authoritativeObligations.length,
      ),
      tc_scenario_coverage: ratio(tcsRendered, tcIds.length),
    },
  }
}

function validateCompositions(compositions, coverageGraph, errors) {
  const coverageNodes = new Map(
    asArray(coverageGraph?.nodes).map((node) => [node.node_id, node]),
  )
  indexBy(asArray(compositions), 'composition_id', 'composition', errors)
  for (const composition of asArray(compositions)) {
    if (composition.status !== 'VALID_COMPOSITION') continue
    if (asArray(composition.component_tc_ids).length < 2) {
      errors.push(`${composition.composition_id} has fewer than two component TCs`)
    }
    for (const tcId of asArray(composition.component_tc_ids)) {
      if (coverageNodes.get(tcId)?.type !== 'TEST_CONDITION') {
        errors.push(`${composition.composition_id} references non-TC ${tcId}`)
      }
    }
    for (const transition of asArray(composition.ordered_transitions)) {
      if (!asArray(transition?.bridge?.evidence).length) {
        errors.push(`${composition.composition_id} has an evidence-free bridge`)
      }
    }
  }
}

export function validateRequirementGraph(
  model,
  ontology,
  patternLibrary,
  coverageSchema,
) {
  const errors = []
  if (!model?.semantic_graph) errors.push('semantic_graph is required')
  if (!model?.coverage_graph) errors.push('coverage_graph is required')
  if (model?.semantic_graph) validateTypedGraph(model.semantic_graph, ontology, errors)
  validatePatternCandidates(model?.pattern_candidates, patternLibrary, errors)
  const counts = model?.coverage_graph
    ? validateCoverageGraph(model.coverage_graph, coverageSchema, errors)
    : {}
  validateCompositions(model?.scenario_compositions, model?.coverage_graph, errors)
  return { status: errors.length ? 'FAIL' : 'PASS', errors, counts }
}

function selfTest() {
  const ontology = parseYaml(defaultOntologyPath)
  const patternLibrary = parseYaml(defaultPatternLibraryPath)
  const coverageSchema = parseYaml(defaultCoverageSchemaPath)
  const valid = {
    pattern_candidates: [
      {
        candidate_id: 'CAND-001',
        pattern_id: 'PAT-NORM-OBLIGATION',
        source_ref: 'prd.md:1',
        matched_text: '系统应返回结果',
        proposed_structure: {},
        status: 'VALIDATED',
      },
    ],
    semantic_graph: {
      nodes: [
        {
          node_id: 'ONT-ACTOR-1',
          type: 'Actor',
          label: '学生',
          properties: { name: '学生' },
          evidence: [{ fact_id: 'FACT-001', source_ref: 'prd.md:1' }],
        },
        {
          node_id: 'ONT-ACTION-1',
          type: 'Action',
          label: '提交答案',
          properties: { verb: '提交' },
          evidence: [{ fact_id: 'FACT-001', source_ref: 'prd.md:1' }],
        },
      ],
      edges: [
        {
          edge_id: 'ONT-EDGE-1',
          type: 'PERFORMS',
          from: 'ONT-ACTOR-1',
          to: 'ONT-ACTION-1',
          evidence: [{ fact_id: 'FACT-001', source_ref: 'prd.md:1' }],
        },
      ],
    },
    coverage_graph: {
      nodes: [
        { node_id: 'SRC-1', type: 'SOURCE', status: 'AUTHORITATIVE' },
        { node_id: 'RG-1', type: 'REQUIREMENT_GROUP', status: 'AUTHORITATIVE' },
        { node_id: 'CL-1', type: 'CLAUSE', status: 'AUTHORITATIVE' },
        { node_id: 'FACT-001', type: 'FACT', status: 'AUTHORITATIVE' },
        { node_id: 'REQ-1', type: 'REQUIREMENT_IR', status: 'ELIGIBLE' },
        { node_id: 'TO-1', type: 'TEST_OBLIGATION', status: 'AUTHORITATIVE' },
        { node_id: 'TC-1', type: 'TEST_CONDITION', status: 'FROZEN' },
        { node_id: 'SC-1', type: 'SCENARIO', status: 'AUTHORITATIVE' },
      ],
      edges: [
        { edge_id: 'C1', type: 'CONTAINS', from: 'SRC-1', to: 'RG-1' },
        { edge_id: 'C2', type: 'CONTAINS', from: 'RG-1', to: 'CL-1' },
        { edge_id: 'C3', type: 'EXTRACTED_AS', from: 'CL-1', to: 'FACT-001' },
        { edge_id: 'C4', type: 'STRUCTURED_AS', from: 'FACT-001', to: 'REQ-1' },
        { edge_id: 'C5', type: 'OBLIGATES', from: 'REQ-1', to: 'TO-1' },
        { edge_id: 'C6', type: 'TESTED_BY', from: 'TO-1', to: 'TC-1' },
        { edge_id: 'C7', type: 'RENDERED_AS', from: 'TC-1', to: 'SC-1' },
      ],
    },
    test_conditions: [{ tc_id: 'TC-1' }],
    scenario_compositions: [],
  }
  const validResult = validateRequirementGraph(
    valid,
    ontology,
    patternLibrary,
    coverageSchema,
  )
  const invalid = structuredClone(valid)
  invalid.semantic_graph.nodes[0].evidence = []
  invalid.coverage_graph.edges.pop()
  const invalidResult = validateRequirementGraph(
    invalid,
    ontology,
    patternLibrary,
    coverageSchema,
  )
  const passed = validResult.status === 'PASS' && invalidResult.status === 'FAIL'
  process.stdout.write(
    `${JSON.stringify({ self_test: passed ? 'PASS' : 'FAIL', validResult, invalidResult }, null, 2)}\n`,
  )
  process.exitCode = passed ? 0 : 1
}

const [
  modelPath,
  ontologyPath = defaultOntologyPath,
  patternLibraryPath = defaultPatternLibraryPath,
  coverageSchemaPath = defaultCoverageSchemaPath,
] = process.argv.slice(2)

if (modelPath === '--self-test') {
  selfTest()
} else if (!modelPath) {
  process.stderr.write(
    'usage: node scripts/validate_requirement_graph.mjs <requirement-model.yaml> ' +
      '[requirement-ontology.yaml] [requirement-patterns.yaml] ' +
      '[coverage-graph-schema.yaml]\n',
  )
  process.exitCode = 2
} else {
  try {
    const result = validateRequirementGraph(
      parseYaml(modelPath),
      parseYaml(ontologyPath),
      parseYaml(patternLibraryPath),
      parseYaml(coverageSchemaPath),
    )
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
    process.exitCode = result.status === 'PASS' ? 0 : 1
  } catch (error) {
    process.stderr.write(`${error.message}\n`)
    process.exitCode = 2
  }
}
