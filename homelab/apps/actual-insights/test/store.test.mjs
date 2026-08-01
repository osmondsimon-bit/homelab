// Persistence tests for locally audited category snapshots and validated memos.
import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
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
    kind: 'long_term',
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
  assert.equal(rows[0].kind, 'long_term');
  assert.equal(rows[0].headline, memo.headline);
  assert.deepEqual(rows[0].payload, payload);
  assert.deepEqual(rows[0].memo, memo);
  assert.deepEqual(rows[0].usage, { input_tokens: 10, output_tokens: 20 });
});

test('migrates the deployed monthly-only schema without losing records', () => {
  const directory = mkdtempSync(join(tmpdir(), 'actual-insights-store-'));
  const path = join(directory, 'insights.sqlite');
  const legacy = new DatabaseSync(path);
  legacy.exec(`
    CREATE TABLE memos (
      id INTEGER PRIMARY KEY,
      month TEXT NOT NULL,
      created_at TEXT NOT NULL,
      snapshot_hash TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      memo_json TEXT NOT NULL,
      model TEXT NOT NULL,
      response_id TEXT NOT NULL,
      usage_json TEXT
    ) STRICT;
    INSERT INTO memos VALUES (
      1, '2026-06', '2026-07-01T00:00:00.000Z', 'hash', '{}',
      '{"headline":"Legacy","summary":"Existing"}', 'model', 'response', NULL
    );
  `);
  legacy.close();

  const store = new MemoStore(path);
  const rows = store.list();
  store.close();

  assert.equal(rows.length, 1);
  assert.equal(rows[0].kind, 'monthly');
  assert.equal(rows[0].headline, 'Legacy');
});
