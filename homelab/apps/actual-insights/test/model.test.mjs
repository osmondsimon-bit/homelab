// Tests for the constrained monthly memo request and response contracts.
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildModelRequest,
  buildTrendModelRequest,
  validateMemo,
  validateTrendMemo,
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
        prior_24_month_average_actual_cents: 45500,
        actual_vs_prior_3_month_basis_points: 2766,
        actual_vs_prior_24_month_basis_points: 3187,
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

const trendPayload = {
  schema_version: 1,
  analysis_type: 'long_term_category_trends',
  start_month: '2024-01',
  end_month: '2025-12',
  currency: 'AUD',
  months_in_period: 24,
  categories: [
    {
      ref: 'c001',
      group: 'Living costs',
      category: 'Groceries',
      type: 'expense',
      months_observed: 24,
      active_in_latest_month: true,
      metrics: {
        total_actual_cents: 516000,
        full_period_average_actual_cents: 21500,
        first_6_month_average_actual_cents: 12500,
        latest_6_month_average_actual_cents: 30500,
        latest_12_month_average_actual_cents: 27500,
        latest_6_vs_first_6_basis_points: 14400,
        annualized_trend_basis_points: 5581,
        variability_basis_points: 3220,
        months_with_budget: 24,
        months_over_budget: 18,
        largest_month_actual_cents: 33000,
        largest_month: '2025-12',
      },
    },
  ],
};

test('builds a no-tools structured request for long-term category trends', () => {
  const request = buildTrendModelRequest({
    payload: trendPayload,
    model: 'gpt-5.6-terra',
  });

  assert.equal(request.store, false);
  assert.equal(request.tools, undefined);
  assert.equal(request.text.format.name, 'actual_long_term_category_memo');
  assert.deepEqual(JSON.parse(request.input.at(-1).content), trendPayload);
});

test('validates long-term findings against locally available evidence', () => {
  const memo = {
    start_month: '2024-01',
    end_month: '2025-12',
    headline: 'Long-term pressure is concentrated',
    summary: 'The category pattern has strengthened across the available history.',
    findings: [
      {
        category_ref: 'c001',
        severity: 'watch',
        pattern: 'rising',
        title: 'A sustained upward pattern merits review',
        observation: 'Recent activity is above the opening portion of the period.',
        evidence: ['first_vs_latest_six', 'annualized_trend', 'budget_frequency'],
        suggested_review: 'Review whether the long-term category allocation still fits.',
      },
    ],
    caveats: ['Category totals cannot explain individual purchases.'],
  };

  assert.deepEqual(validateTrendMemo({ memo, payload: trendPayload }), memo);
  memo.findings[0].evidence = ['unknown'];
  assert.throws(
    () => validateTrendMemo({ memo, payload: trendPayload }),
    /unknown trend evidence type/,
  );
});
