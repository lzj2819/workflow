#!/usr/bin/env node
import { buildBundle } from './gherkin_flow.mjs'

function option(name) {
  const index = process.argv.indexOf(name)
  return index === -1 ? null : process.argv[index + 1]
}

const prdPath = option('--prd')
const outputPath = option('--out')
if (!prdPath || !outputPath) {
  process.stderr.write('usage: node scripts/run_gherkin_flow.mjs --prd <canonical-prd.json> --out <new-bundle-dir>\n')
  process.exit(2)
}

try {
  const result = buildBundle(prdPath, outputPath)
  process.stdout.write(`${JSON.stringify({ status: 'STRUCTURE_PASS', output: result.outputPath, files: result.manifest.bundle_files }, null, 2)}\n`)
} catch (error) {
  process.stderr.write(`${error.message}\n`)
  process.exitCode = error.message.startsWith('GENERATION_BLOCKED:') ? 1 : 2
}
