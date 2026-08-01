// Persistence tests for locally audited category snapshots and validated memos.
import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import { MemoStore } from '../src/store.mjs';

test('stores and reads a validated monthly memo without secrets', () => {
  const directory = mkdtempSync(join(tmpdir(), 'actual-insights-store-'));
  const store = new MemoStore(join(directory, 'insights.sqlite'));
  const payload = {
    schema_version: 1,
    target_month: '2026-06',
    currency: 'AUD',
    categories: [],
  };
  const memo = {
    month: '2026-06',
    headline: 'A category needs review',
    summary: 'Review the local evidence.',
    findings: [],
    caveats: [],
  };

  const id = store.save({
    month: '2026-06',
    snapshotHash: 'abc123',
    payload,
    memo,
    model: 'gpt-5.6-terra',
    responseId: 'resp_123',
    usage: { input_tokens: 10, output_tokens: 20 },
  });
  const rows = store.list();
  store.close();

  assert.equal(id, 1);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].month, '2026-06');
  assert.equal(rows[0].headline, memo.headline);
  assert.deepEqual(rows[0].payload, payload);
  assert.deepEqual(rows[0].memo, memo);
  assert.deepEqual(rows[0].usage, { input_tokens: 10, output_tokens: 20 });
});
