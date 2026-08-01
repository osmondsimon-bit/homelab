// Tests for the narrow, ephemeral Actual API adapter.
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';

import {
  extractCategoryMonths,
  extractCompletedCategoryHistory,
} from '../src/actual-client.mjs';

test('uses only budget reads and removes the decrypted cache', async () => {
  const root = mkdtempSync(join(tmpdir(), 'actual-insights-test-'));
  const calls = [];
  const api = {
    async init(config) {
      calls.push(['init', config]);
      writeFileSync(join(config.dataDir, 'decrypted-marker'), 'sensitive');
    },
    async downloadBudget(syncId, options) {
      calls.push(['downloadBudget', syncId, options]);
    },
    async getBudgetMonths() {
      calls.push(['getBudgetMonths']);
      return ['2026-04', '2026-05', '2026-06'];
    },
    async getBudgetMonth(month) {
      calls.push(['getBudgetMonth', month]);
      return { month, categoryGroups: [] };
    },
    async shutdown() {
      calls.push(['shutdown']);
    },
  };

  const result = await extractCategoryMonths({
    api,
    targetMonth: '2026-06',
    historyMonths: 2,
    currency: 'AUD',
    cacheRoot: root,
    serverUrl: 'http://actual:5006',
    serverPassword: 'server-secret',
    syncId: 'sync-secret',
    encryptionPassword: 'encryption-secret',
  });

  assert.equal(result.currency, 'AUD');
  assert.deepEqual(result.budgetMonths.map(month => month.month), [
    '2026-04',
    '2026-05',
    '2026-06',
  ]);
  assert.deepEqual(calls.map(call => call[0]), [
    'init',
    'downloadBudget',
    'getBudgetMonths',
    'getBudgetMonth',
    'getBudgetMonth',
    'getBudgetMonth',
    'shutdown',
  ]);
  assert.equal(existsSync(root), false);
});

test('shuts down and removes the cache when Actual fails', async () => {
  const root = mkdtempSync(join(tmpdir(), 'actual-insights-test-'));
  let shutdown = false;
  const api = {
    async init() {},
    async downloadBudget() {
      throw new Error('decrypt-failure: sensitive detail');
    },
    async shutdown() {
      shutdown = true;
    },
  };

  await assert.rejects(
    extractCategoryMonths({
      api,
      targetMonth: '2026-06',
      historyMonths: 12,
      currency: 'AUD',
      cacheRoot: root,
      serverUrl: 'http://actual:5006',
      serverPassword: 'server-secret',
      syncId: 'sync-secret',
      encryptionPassword: 'encryption-secret',
    }),
    /Actual category extraction failed/,
  );
  assert.equal(shutdown, true);
  assert.equal(existsSync(root), false);
});

test('extracts the latest twenty-four completed budget months for the initial trend', async () => {
  const root = mkdtempSync(join(tmpdir(), 'actual-insights-test-'));
  const availableMonths = Array.from({ length: 26 }, (_, index) =>
    new Date(Date.UTC(2024, 6 + index, 1)).toISOString().slice(0, 7),
  );
  const requested = [];
  const api = {
    async init() {},
    async downloadBudget() {},
    async getBudgetMonths() {
      return availableMonths;
    },
    async getBudgetMonth(month) {
      requested.push(month);
      return { month, categoryGroups: [] };
    },
    async shutdown() {},
  };

  const result = await extractCompletedCategoryHistory({
    api,
    completedBeforeMonth: '2026-08',
    historyMonths: 24,
    currency: 'AUD',
    cacheRoot: root,
    serverUrl: 'http://actual:5006',
    serverPassword: 'server-secret',
    syncId: 'sync-secret',
    encryptionPassword: 'encryption-secret',
  });

  assert.equal(result.budgetMonths.length, 24);
  assert.equal(requested[0], '2024-08');
  assert.equal(requested.at(-1), '2026-07');
  assert.equal(requested.includes('2026-08'), false);
  assert.equal(existsSync(root), false);
});
