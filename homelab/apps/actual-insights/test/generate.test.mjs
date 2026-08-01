// End-to-end orchestration tests with Actual and OpenAI replaced by local fakes.
import assert from 'node:assert/strict';
import test from 'node:test';

import { createMemoGenerator } from '../src/generate.mjs';

test('persists one manually requested category memo and prevents overlap', async () => {
  const saves = [];
  let releaseExtraction;
  const extractionStarted = new Promise(resolve => {
    releaseExtraction = resolve;
  });
  let continueExtraction;
  const extractionBlocked = new Promise(resolve => {
    continueExtraction = resolve;
  });
  const extract = async () => {
    releaseExtraction();
    await extractionBlocked;
    return {
      currency: 'AUD',
      budgetMonths: [
        {
          month: '2026-06',
          categoryGroups: [
            {
              name: 'Living costs',
              is_income: false,
              categories: [
                { id: 'local-only', name: 'Groceries', budgeted: 50000, spent: -52000, balance: -2000 },
              ],
            },
          ],
        },
      ],
    };
  };
  const request = async ({ payload }) => ({
    memo: {
      month: payload.target_month,
      headline: 'Review a category pattern',
      summary: 'The highlighted category merits review.',
      findings: [],
      caveats: [],
    },
    responseId: 'resp_test',
    model: 'gpt-5.6-terra',
    usage: null,
  });
  const store = {
    save(value) {
      saves.push(value);
      return 7;
    },
  };
  const generate = createMemoGenerator({ extract, request, store, model: 'gpt-5.6-terra' });

  const first = generate('2026-06');
  await extractionStarted;
  await assert.rejects(generate('2026-06'), /already in progress/);
  continueExtraction();
  const result = await first;

  assert.equal(result.id, 7);
  assert.equal(saves.length, 1);
  assert.equal(saves[0].payload.categories[0].ref, 'c001');
  assert.equal(JSON.stringify(saves[0].payload).includes('local-only'), false);
});

test('refuses the current or a future month', async () => {
  const currentMonth = new Date().toISOString().slice(0, 7);
  const generate = createMemoGenerator({
    extract: async () => assert.fail('Actual must not be called for an incomplete month'),
    request: async () => assert.fail('the model must not be called for an incomplete month'),
    store: { save: () => assert.fail('an incomplete month must not be stored') },
    model: 'gpt-5.6-terra',
  });

  await assert.rejects(generate(currentMonth), /requires a completed month/);
});
