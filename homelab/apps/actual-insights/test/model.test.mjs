// Tests for the constrained monthly memo request and response contracts.
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildModelRequest,
  validateMemo,
} from '../src/model.mjs';

const payload = {
  schema_version: 1,
  target_month: '2026-06',
  currency: 'AUD',
  categories: [
    {
      ref: 'c001',
      group: 'Living costs',
      category: 'Groceries',
      type: 'expense',
      months_of_history: 6,
      target: {
        budgeted_cents: 52000,
        actual_cents: 60000,
        balance_cents: -3000,
      },
      comparisons: {
        previous_month_actual_cents: 45000,
        prior_3_month_average_actual_cents: 47000,
        prior_12_month_average_actual_cents: 46000,
        actual_vs_prior_3_month_basis_points: 2766,
        budget_variance_cents: -8000,
      },
    },
  ],
};

test('sends only the category payload to the model with storage disabled', () => {
  const request = buildModelRequest({
    payload,
    model: 'gpt-5.6-terra',
  });

  assert.equal(request.model, 'gpt-5.6-terra');
  assert.equal(request.store, false);
  assert.deepEqual(request.reasoning, { effort: 'low' });
  assert.equal(request.tools, undefined);
  assert.equal(request.text.format.type, 'json_schema');
  assert.equal(request.text.format.strict, true);

  const userInput = request.input.find(item => item.role === 'user').content;
  assert.deepEqual(JSON.parse(userInput), payload);
  for (const forbidden of ['transaction', 'payee', 'account', 'schedule', 'note']) {
    assert.equal(userInput.toLowerCase().includes(forbidden), false, forbidden);
  }
});

test('accepts a memo that references known category evidence', () => {
  const memo = {
    month: '2026-06',
    headline: 'Spending pressure is concentrated in one category',
    summary: 'Review the highlighted category before setting the next budget.',
    findings: [
      {
        category_ref: 'c001',
        severity: 'watch',
        title: 'Groceries moved above their recent pattern',
        observation: 'Activity is above its recent baseline and assigned budget.',
        evidence: ['actual_vs_prior_3_month', 'budget_variance'],
        suggested_review: 'Check whether the next category allocation still reflects current needs.',
      },
    ],
    caveats: ['This memo uses category totals and cannot explain individual purchases.'],
  };

  assert.deepEqual(validateMemo({ memo, payload }), memo);
});

test('rejects unknown category references and numeric claims in model prose', () => {
  const base = {
    month: '2026-06',
    headline: 'Review the monthly category pattern',
    summary: 'One category merits attention.',
    findings: [
      {
        category_ref: 'unknown',
        severity: 'watch',
        title: 'Category pattern changed',
        observation: 'Activity is above its recent baseline.',
        evidence: ['actual_vs_prior_3_month'],
        suggested_review: 'Check whether the category plan still fits.',
      },
    ],
    caveats: ['Category totals do not explain individual purchases.'],
  };

  assert.throws(() => validateMemo({ memo: base, payload }), /unknown category_ref/);
  base.findings[0].category_ref = 'c001';
  base.summary = 'Spending rose by 27 percent.';
  assert.throws(() => validateMemo({ memo: base, payload }), /numeric model prose/);
});
