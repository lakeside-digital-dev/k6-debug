'use strict';

const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const generate = require('@babel/generator').default;
const t = require('@babel/types');
const plugin = require('./plugin');

const TS_EXT = /\.(ts|mts|cts)$/i;

/**
 * Instruments a k6 script (JavaScript or TypeScript) for debugging.
 * TypeScript syntax is kept as-is: k6 itself strips types when the
 * instrumented file keeps a .ts extension.
 *
 * @param {string} source   script source
 * @param {string} filename absolute path of the ORIGINAL script; it is
 *                          embedded in every hook so breakpoints map back to it
 * @param {object} [opts]   { sourceMaps: boolean }
 * @returns {string} instrumented code (line numbers retained)
 */
function instrument(source, filename, opts) {
  opts = opts || {};
  const plugins = ['dynamicImport'];
  if (TS_EXT.test(filename)) plugins.push('typescript');

  const ast = parser.parse(source, {
    sourceType: 'module',
    plugins: plugins,
    sourceFilename: filename,
  });

  const pluginInstance = plugin({ types: t });
  traverse(ast, pluginInstance.visitor, undefined, {
    filename: filename,
    file: { opts: { filename: filename } },
  });

  return generate(
    ast,
    {
      sourceMaps: opts.sourceMaps ? 'inline' : false,
      sourceFileName: filename,
      retainLines: true,
    },
    source
  ).code;
}

module.exports = { instrument };
