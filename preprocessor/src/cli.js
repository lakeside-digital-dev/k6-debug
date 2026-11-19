'use strict';

const fs = require('fs');
const path = require('path');
const { instrument } = require('./instrument');

function usage() {
  console.error(
    'Usage: k6-debug-preprocess <input.js> [-o output.js] [--source-maps]'
  );
  console.error('  If -o is omitted, prints to stdout.');
  console.error('  --source-maps generates an inline source map.');
  process.exit(1);
}

function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    usage();
  }

  let inputFile = null;
  let outputFile = null;
  let sourceMaps = false;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '-o' && i + 1 < args.length) {
      outputFile = args[++i];
    } else if (args[i] === '--source-maps') {
      sourceMaps = true;
    } else if (args[i].startsWith('-')) {
      console.error(`Unknown option: ${args[i]}`);
      usage();
    } else {
      inputFile = args[i];
    }
  }

  if (!inputFile) {
    console.error('Error: input file is required');
    usage();
  }

  const source = fs.readFileSync(inputFile, 'utf-8');
  const filename = path.resolve(inputFile);
  const output = { code: instrument(source, filename, { sourceMaps }) };

  if (outputFile) {
    fs.writeFileSync(outputFile, output.code, 'utf-8');
    console.error(`[k6-debug-preprocess] Written to ${outputFile}`);
  } else {
    process.stdout.write(output.code);
  }
}

main();
