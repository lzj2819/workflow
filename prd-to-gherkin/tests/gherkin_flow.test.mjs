import assert from 'node:assert/strict'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import test from 'node:test'

import {
  BUNDLE_FILES,
  buildBundle,
  canonicalJson,
  compilePrd,
  renderFeature,
  validateBundle,
  validateProjection,
} from '../scripts/gherkin_flow.mjs'
import { readyPrd } from './fixtures.mjs'

function source(prd) {
  return Buffer.from(canonicalJson(prd), 'utf8')
}

test('compiles functional main/boundary/exception and NFR scenarios', () => {
  const prd = readyPrd()
  const model = compilePrd(prd, source(prd))
  assert.equal(model.artifact_schema_version, 'testcases/v2')
  assert.deepEqual(model.testcases.map((item) => item.kind), ['nfr', 'main', 'boundary', 'exception'])
  assert.deepEqual(model.requirement_ids, ['NFR-NOTE-LATENCY', 'REQ-NOTE-CREATE'])
  for (const testcase of model.testcases) {
    assert.equal(testcase.steps.filter((item) => item.phase === 'when').length, 1)
    assert.equal(testcase.steps.filter((item) => item.phase === 'given')[0].keyword, 'Given')
    assert.equal(testcase.steps.filter((item) => item.phase === 'then')[0].keyword, 'Then')
  }
  const feature = renderFeature(model)
  const validation = validateProjection(model, feature)
  assert.equal(validation.status, 'STRUCTURE_PASS', validation.errors.join('\n'))
  assert.doesNotMatch(feature, /Scenario Outline|Examples:|Background:/u)
})

test('input order does not change testcase order or semantic content', () => {
  const original = readyPrd()
  const shuffled = structuredClone(original)
  shuffled.payload.requirements.reverse()
  shuffled.requirement_ids.reverse()
  shuffled.requirements.reverse()
  shuffled.payload.oracle_coverage_ledger.reverse()
  shuffled.payload.acceptance_contracts.reverse()
  const first = compilePrd(original, source(original))
  const second = compilePrd(shuffled, source(shuffled))
  assert.deepEqual(second.testcases, first.testcases)
  assert.deepEqual(second.requirement_ids, first.requirement_ids)
})

test('different content keeps the same model and Feature skeleton', () => {
  const firstPrd = readyPrd()
  const secondPrd = readyPrd()
  secondPrd.payload.acceptance_contracts[0].actor = '管理员'
  const first = compilePrd(firstPrd, source(firstPrd))
  const second = compilePrd(secondPrd, source(secondPrd))
  assert.deepEqual(Object.keys(second), Object.keys(first))
  assert.deepEqual(Object.keys(second.testcases[0]), Object.keys(first.testcases[0]))
  const skeleton = (text) => text.split('\n').map((line) => line.replace(/: .+$/u, ': <content>'))
  assert.equal(skeleton(renderFeature(first)).length, skeleton(renderFeature(second)).length)
})

test('normalizes Unicode and multiline PRD text to NFC single-line steps', () => {
  const prd = readyPrd()
  prd.payload.acceptance_contracts[0].actor = 'Cafe\u0301\r\n用户'
  const feature = renderFeature(compilePrd(prd, source(prd)))
  assert.match(feature, /actor: Café 用户/u)
  assert.doesNotMatch(feature, /\r/u)
})

test('blocks missing oracle facts rather than inventing a testcase', () => {
  const prd = readyPrd()
  prd.payload.acceptance_contracts[0].observable_oracles = []
  assert.throws(() => compilePrd(prd, source(prd)), /GENERATION_BLOCKED:[\s\S]*observable_oracles/u)
})

test('preserves approved quoted UNKNOWN literals but blocks unresolved UNKNOWN', () => {
  const approved = readyPrd()
  approved.payload.acceptance_contracts[0].actor = '协议字面值 "UNKNOWN" 的用户'
  const approvedModel = compilePrd(approved, source(approved))
  assert.equal(validateProjection(approvedModel, renderFeature(approvedModel)).status, 'STRUCTURE_PASS')

  const unresolved = readyPrd()
  unresolved.payload.acceptance_contracts[0].actor = 'UNKNOWN 用户'
  const unresolvedModel = compilePrd(unresolved, source(unresolved))
  assert.equal(validateProjection(unresolvedModel, renderFeature(unresolvedModel)).status, 'STRUCTURE_FAIL')
})

test('writes exactly one deterministic five-file bundle and detects tampering', () => {
  const temporary = mkdtempSync(join(tmpdir(), 'prd-to-gherkin-test-'))
  try {
    const prdPath = join(temporary, 'prd.json')
    const renamedPrdPath = join(temporary, 'same-content-different-name.json')
    writeFileSync(prdPath, canonicalJson(readyPrd()), 'utf8')
    writeFileSync(renamedPrdPath, canonicalJson(readyPrd()), 'utf8')
    const firstPath = join(temporary, 'bundle-a')
    const secondPath = join(temporary, 'bundle-b')
    buildBundle(prdPath, firstPath)
    buildBundle(renamedPrdPath, secondPath)
    assert.deepEqual(BUNDLE_FILES.slice().sort(), ['quality_report.md', 'testcases.feature', 'testcases.json', 'testcases_manifest.json', 'validation_report.json'])
    for (const name of BUNDLE_FILES) {
      assert.deepEqual(readFileSync(join(firstPath, name)), readFileSync(join(secondPath, name)), name)
    }
    assert.equal(validateBundle(firstPath).status, 'STRUCTURE_PASS')
    writeFileSync(join(firstPath, 'testcases.feature'), `${readFileSync(join(firstPath, 'testcases.feature'), 'utf8')}# drift\n`, 'utf8')
    assert.equal(validateBundle(firstPath).status, 'STRUCTURE_FAIL')
  } finally {
    rmSync(temporary, { recursive: true, force: true })
  }
})
