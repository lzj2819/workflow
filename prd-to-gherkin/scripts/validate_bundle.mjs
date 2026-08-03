#!/usr/bin/env node
import { validateBundle } from './gherkin_flow.mjs'

const index = process.argv.indexOf('--bundle')
const bundle = index === -1 ? null : process.argv[index + 1]
if (!bundle) {
  process.stderr.write('usage: node scripts/validate_bundle.mjs --bundle <bundle-dir>\n')
  process.exit(2)
}

try {
  const result = validateBundle(bundle)
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
  process.exitCode = result.status === 'STRUCTURE_PASS' ? 0 : 1
} catch (error) {
  process.stderr.write(`${error.message}\n`)
  process.exitCode = 2
}
