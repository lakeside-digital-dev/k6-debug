'use strict';
// Entry point for the bundle that is embedded into the k6-debug binary
// (see ../../instrument). It runs inside sobek, so Node.js is not required.
const { instrument } = require('./instrument');

globalThis.k6DebugInstrument = function (source, filename) {
  return instrument(source, filename);
};
