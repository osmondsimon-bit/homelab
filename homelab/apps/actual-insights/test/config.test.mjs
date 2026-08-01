// Configuration tests keep exceptional spend classification explicit and bounded.
import assert from 'node:assert/strict';
import test from 'node:test';

import { parseExceptionalCategories } from '../src/config.mjs';

test('parses and de-duplicates exact exceptional category names', () => {
  assert.deepEqual(
    parseExceptionalCategories('["House Build","Rent","Rent"]'),
    ['House Build', 'Rent'],
  );
});

test('rejects malformed exceptional category configuration', () => {
  assert.throws(() => parseExceptionalCategories('House Build,Rent'), /JSON array/);
  assert.throws(() => parseExceptionalCategories('{"name":"Rent"}'), /category names/);
  assert.throws(() => parseExceptionalCategories('[""]'), /category names/);
});
