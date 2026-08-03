#!/usr/bin/env node
/** Compatibility CLI for callers that validate a Feature projection directly. */
import { readFileSync } from 'node:fs'

import { validateProjection } from './gherkin_flow.mjs'

const [featurePath, testcasesPath] = process.argv.slice(2)
if (!featurePath || !testcasesPath) {
  process.stderr.write(
    'usage: node scripts/validate_feature.mjs <testcases.feature> <testcases.json>\n',
  )
  process.exit(2)
}

try {
  const featureText = readFileSync(featurePath, 'utf8')
  const model = JSON.parse(readFileSync(testcasesPath, 'utf8'))
  const result = validateProjection(model, featureText)
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
  process.exitCode = result.status === 'STRUCTURE_PASS' ? 0 : 1
} catch (error) {
  process.stderr.write(`${error.message}\n`)
  process.exitCode = 2
}
