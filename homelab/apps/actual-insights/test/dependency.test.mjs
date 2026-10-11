// Reject untrusted Handlebars AST data before generated JavaScript can execute.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const Handlebars = require('handlebars');

test('rejects compiler AST data that attempts to execute a marker expression', () => {
  const loc = { start: { line: 1, column: 0 } };
  const ast = {
    type: 'Program', loc,
    body: [{
      type: 'BlockStatement', loc,
      path: { type: 'PathExpression', data: false, depth: 0, parts: ['missingHelper'], original: 'missingHelper', loc },
      params: [],
      program: {
        type: 'Program', loc, body: [],
        blockParams: { length: '(()=>{globalThis.__insightsCompilerMarker=true;return 0})()' },
      },
      openStrip: { open: false, close: false },
      closeStrip: { open: false, close: false },
    }],
  };
  delete globalThis.__insightsCompilerMarker;
  try {
    try { Handlebars.compile(ast)({}); } catch { /* Invalid ASTs should be rejected. */ }
    assert.equal(globalThis.__insightsCompilerMarker, undefined, 'untrusted AST data executed as JavaScript');
  } finally {
    delete globalThis.__insightsCompilerMarker;
  }
});
