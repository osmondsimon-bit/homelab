// Tests for the constrained monthly memo request and response contracts.
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  buildModelRequest,
  buildTrendModelRequest,
  memoSchema,
  requestTrendMemo,
  trendMemoSchema,
  validateMemo,
  validateTrendMemo,
} from '../src/model.mjs';

function schemaKeywords(value, found = new Set()) {
  if (!value || typeof value !== 'object') return found;
  for (const [key, child] of Object.entries(value)) {
    found.add(key);
    schemaKeywords(child, found);
  }
  return found;
}

test('uses only constraints accepted by OpenAI Structured Outputs', () => {
  const unsupported = ['minLength', 'maxLength', 'uniqueItems'];
  for (const schema of [memoSchema, trendMemoSchema]) {
    const keywords = schemaKeywords(schema);
    for (const keyword of unsupported) {
      assert.equal(keywords.has(keyword), false, keyword);
    }
  }
});

const payload = {
  schema_version: 2,
  analysis_mode: 'budget_and_spend',
  target_month: '2026-06',
  currency: 'AUD',
  categories: [
    {
      ref: 'c001',
      group: 'Living costs',
      category: 'Groceries',
      type: 'expense',
      months_of_history: 6,
      available_evidence: [
        'target_actual',
        'target_budgeted',
        'target_balance',
        'previous_month_actual',
        'actual_vs_prior_3_month',
        'actual_vs_prior_12_month',
        'actual_vs_prior_24_month',
        'budget_variance',
      ],
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
  assert.match(request.input[0].content, /available_evidence/);

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

test('rejects budget language in a spend-only monthly memo', () => {
  const spendOnlyPayload = structuredClone(payload);
  spendOnlyPayload.analysis_mode = 'spend_only';
  spendOnlyPayload.categories[0].available_evidence = ['target_actual'];
  spendOnlyPayload.categories[0].target.budgeted_cents = null;
  spendOnlyPayload.categories[0].target.balance_cents = null;
  spendOnlyPayload.categories[0].comparisons.budget_variance_cents = null;
  const memo = {
    month: '2026-06',
    headline: 'Budget pressure merits attention',
    summary: 'The category moved above its recent pattern.',
    findings: [],
    caveats: [],
  };

  assert.throws(
    () => validateMemo({ memo, payload: spendOnlyPayload }),
    /budget language is not permitted/,
  );
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

test('enforces prose lengths and unique evidence outside the model schema', () => {
  const memo = {
    month: '2026-06',
    headline: 'A'.repeat(121),
    summary: 'Review the monthly category pattern.',
    findings: [
      {
        category_ref: 'c001',
        severity: 'watch',
        title: 'Category pattern changed',
        observation: 'Activity is above its recent baseline.',
        evidence: ['actual_vs_prior_3_month', 'actual_vs_prior_3_month'],
        suggested_review: 'Check whether the category plan still fits.',
      },
    ],
    caveats: ['Category totals do not explain individual purchases.'],
  };

  assert.throws(() => validateMemo({ memo, payload }), /headline is too long/);
  memo.headline = 'Review the monthly category pattern';
  assert.throws(() => validateMemo({ memo, payload }), /evidence must be unique/);
});

const trendPayload = {
  schema_version: 2,
  analysis_type: 'long_term_category_trends',
  analysis_mode: 'budget_and_spend',
  start_month: '2024-01',
  end_month: '2025-12',
  currency: 'AUD',
  months_in_period: 24,
  spend_summary: {
    latest_12_total_actual_cents: 330000,
    previous_12_total_actual_cents: 186000,
    latest_12_underlying_actual_cents: 330000,
    previous_12_underlying_actual_cents: 186000,
    latest_12_average_monthly_underlying_cents: 27500,
    latest_12_median_monthly_underlying_cents: 27500,
    latest_12_standard_deviation_monthly_underlying_cents: 3452,
    latest_12_vs_previous_12_underlying_basis_points: 7742,
    latest_12_exceptional_actual_cents: 0,
  },
  categories: [
    {
      ref: 'c001',
      group: 'Living costs',
      category: 'Groceries',
      type: 'expense',
      months_observed: 24,
      active_in_latest_month: true,
      is_exceptional: false,
      available_evidence: [
        'full_period_average',
        'first_vs_latest_six',
        'latest_twelve',
        'latest_twelve_total',
        'previous_twelve_total',
        'latest_vs_previous_twelve',
        'monthly_median',
        'monthly_deviation',
        'active_month_average',
        'annualized_trend',
        'variability',
        'budget_frequency',
        'largest_month',
        'observation_coverage',
      ],
      metrics: {
        total_actual_cents: 516000,
        full_period_average_actual_cents: 21500,
        first_6_month_average_actual_cents: 12500,
        latest_6_month_average_actual_cents: 30500,
        latest_12_month_average_actual_cents: 27500,
        latest_12_total_actual_cents: 330000,
        previous_12_total_actual_cents: 186000,
        previous_12_month_average_actual_cents: 15500,
        latest_12_median_actual_cents: 27500,
        latest_12_standard_deviation_cents: 3452,
        latest_12_active_month_average_actual_cents: 27500,
        latest_12_active_months: 12,
        latest_12_vs_previous_12_basis_points: 7742,
        latest_6_vs_first_6_basis_points: 14400,
        annualized_trend_basis_points: 5581,
        variability_basis_points: 3220,
        months_with_positive_budget: 24,
        months_over_positive_budget: 18,
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
  assert.match(request.input[0].content, /analysis_mode is spend_only/);
});

test('rejects budget language and budget pressure in spend-only analysis', () => {
  const spendOnlyPayload = structuredClone(trendPayload);
  spendOnlyPayload.analysis_mode = 'spend_only';
  spendOnlyPayload.categories[0].available_evidence = ['latest_twelve_total'];
  spendOnlyPayload.categories[0].metrics.months_with_positive_budget = 0;
  spendOnlyPayload.categories[0].metrics.months_over_positive_budget = 0;
  const memo = {
    start_month: '2024-01',
    end_month: '2025-12',
    headline: 'Budget pressure deserves attention',
    summary: 'The category has a sustained pattern.',
    findings: [],
    caveats: [],
  };

  assert.throws(
    () => validateTrendMemo({ memo, payload: spendOnlyPayload }),
    /budget language is not permitted/,
  );
  memo.headline = 'Spending pressure deserves attention';
  memo.findings = [{
    category_ref: 'c001',
    severity: 'watch',
    pattern: 'budget_pressure',
    title: 'The category has a sustained pattern',
    observation: 'Activity remains elevated.',
    evidence: ['latest_twelve_total'],
    suggested_review: 'Review the category pattern.',
  }];
  assert.throws(
    () => validateTrendMemo({ memo, payload: spendOnlyPayload }),
    /budget pressure is not permitted/,
  );
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

test('rejects trend evidence outside the category availability allowlist', () => {
  const limitedPayload = structuredClone(trendPayload);
  limitedPayload.categories[0].available_evidence = [
    'full_period_average',
    'observation_coverage',
  ];
  const memo = {
    start_month: '2024-01',
    end_month: '2025-12',
    headline: 'Limited history requires care',
    summary: 'The available category history supports only a narrow observation.',
    findings: [
      {
        category_ref: 'c001',
        severity: 'info',
        pattern: 'limited_history',
        title: 'The short record limits interpretation',
        observation: 'Only the available history should guide review.',
        evidence: ['first_vs_latest_six'],
        suggested_review: 'Wait for more category history before drawing a direction.',
      },
    ],
    caveats: ['Coverage is limited for this category.'],
  };

  assert.throws(
    () => validateTrendMemo({ memo, payload: limitedPayload }),
    /outside available_evidence/,
  );
});

test('retries one locally invalid trend response without retrying API errors', async () => {
  const validMemo = {
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
        evidence: ['first_vs_latest_six', 'annualized_trend'],
        suggested_review: 'Review whether the long-term category allocation still fits.',
      },
    ],
    caveats: ['Category totals cannot explain individual purchases.'],
  };
  const invalidMemo = { ...validMemo, summary: 'Activity increased by 25 percent.' };
  const responses = [invalidMemo, validMemo];
  let calls = 0;
  const client = {
    responses: {
      create: async () => ({
        id: `response-${calls}`,
        model: 'gpt-5.6-terra',
        output_text: JSON.stringify(responses[calls++]),
        usage: null,
      }),
    },
  };

  const result = await requestTrendMemo({
    client,
    payload: trendPayload,
    model: 'gpt-5.6-terra',
  });
  assert.equal(calls, 2);
  assert.deepEqual(result.memo, validMemo);

  const apiError = Object.assign(new Error('provider unavailable'), { code: 'api_error' });
  const failingClient = { responses: { create: async () => { throw apiError; } } };
  await assert.rejects(
    requestTrendMemo({
      client: failingClient,
      payload: trendPayload,
      model: 'gpt-5.6-terra',
    }),
    error => error === apiError,
  );
});

test('classifies repeated invalid trend output without exposing model prose', async () => {
  let calls = 0;
  const client = {
    responses: {
      create: async () => {
        calls += 1;
        return {
          id: `invalid-${calls}`,
          model: 'gpt-5.6-terra',
          output_text: '{"sensitive":"unvalidated model prose"}',
          usage: null,
        };
      },
    },
  };

  await assert.rejects(
    requestTrendMemo({ client, payload: trendPayload, model: 'gpt-5.6-terra' }),
    error => {
      assert.equal(error.code, 'model_output_invalid');
      assert.equal(error.message.includes('sensitive'), false);
      return true;
    },
  );
  assert.equal(calls, 2);
});
