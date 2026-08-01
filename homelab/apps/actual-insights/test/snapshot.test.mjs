// Regression tests for the category-only Actual Budget snapshot boundary.
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  assertCategoryOnlyPayload,
  assertTrendOnlyPayload,
  buildCategoryPayload,
  buildTrendPayload,
} from '../src/snapshot.mjs';

const months = [
  {
    month: '2026-05',
    categoryGroups: [
      {
        id: 'group-secret-id',
        name: 'Living costs',
        is_income: false,
        categories: [
          {
            id: 'category-secret-id',
            group_id: 'group-secret-id',
            name: 'Groceries',
            hidden: false,
            budgeted: 50000,
            spent: -45000,
            balance: 5000,
            carryover: false,
          },
        ],
      },
      {
        id: 'income-group-secret-id',
        name: 'Income',
        is_income: true,
        categories: [
          {
            id: 'income-category-secret-id',
            group_id: 'income-group-secret-id',
            name: 'Salary',
            received: 400000,
          },
        ],
      },
    ],
    accounts: [{ id: 'must-never-leak', name: 'Everyday account' }],
    transactions: [{ payee_name: 'Must never leak' }],
  },
  {
    month: '2026-06',
    categoryGroups: [
      {
        id: 'group-secret-id',
        name: 'Living costs',
        is_income: false,
        categories: [
          {
            id: 'category-secret-id',
            group_id: 'group-secret-id',
            name: 'Groceries',
            hidden: false,
            budgeted: 52000,
            spent: -60000,
            balance: -3000,
            carryover: true,
          },
        ],
      },
      {
        id: 'income-group-secret-id',
        name: 'Income',
        is_income: true,
        categories: [
          {
            id: 'income-category-secret-id',
            group_id: 'income-group-secret-id',
            name: 'Salary',
            received: 410000,
          },
        ],
      },
    ],
  },
];

test('builds a monthly payload containing category aggregates only', () => {
  const payload = buildCategoryPayload({
    targetMonth: '2026-06',
    currency: 'AUD',
    budgetMonths: months,
  });

  assert.equal(payload.schema_version, 1);
  assert.equal(payload.target_month, '2026-06');
  assert.equal(payload.currency, 'AUD');
  assert.deepEqual(payload.categories, [
    {
      ref: 'c001',
      group: 'Income',
      category: 'Salary',
      type: 'income',
      months_of_history: 1,
      available_evidence: [
        'target_actual',
        'previous_month_actual',
        'actual_vs_prior_3_month',
        'actual_vs_prior_12_month',
        'actual_vs_prior_24_month',
      ],
      target: {
        budgeted_cents: null,
        actual_cents: 410000,
        balance_cents: null,
      },
      comparisons: {
        previous_month_actual_cents: 400000,
        prior_3_month_average_actual_cents: 400000,
        prior_12_month_average_actual_cents: 400000,
        prior_24_month_average_actual_cents: 400000,
        actual_vs_prior_3_month_basis_points: 250,
        actual_vs_prior_24_month_basis_points: 250,
        budget_variance_cents: null,
      },
    },
    {
      ref: 'c002',
      group: 'Living costs',
      category: 'Groceries',
      type: 'expense',
      months_of_history: 1,
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
        prior_3_month_average_actual_cents: 45000,
        prior_12_month_average_actual_cents: 45000,
        prior_24_month_average_actual_cents: 45000,
        actual_vs_prior_3_month_basis_points: 3333,
        actual_vs_prior_24_month_basis_points: 3333,
        budget_variance_cents: -8000,
      },
    },
  ]);

  assert.doesNotThrow(() => assertCategoryOnlyPayload(payload));
  const serialized = JSON.stringify(payload);
  for (const forbidden of [
    'secret-id',
    'account',
    'transaction',
    'payee',
    'notes',
    'schedule',
    'carryover',
    'hidden',
  ]) {
    assert.equal(serialized.toLowerCase().includes(forbidden), false, forbidden);
  }
});

test('rejects any field outside the category-only allowlist', () => {
  const payload = buildCategoryPayload({
    targetMonth: '2026-06',
    currency: 'AUD',
    budgetMonths: months,
  });

  payload.categories[0].payee = 'Injected merchant';
  assert.throws(
    () => assertCategoryOnlyPayload(payload),
    /category-only payload contains unexpected field: payee/,
  );
});

test('bounds category labels and payload size before model submission', () => {
  const payload = buildCategoryPayload({
    targetMonth: '2026-06',
    currency: 'AUD',
    budgetMonths: months,
  });

  payload.categories[0].category = 'x'.repeat(201);
  assert.throws(
    () => assertCategoryOnlyPayload(payload),
    /category labels must contain between one and 200 characters/,
  );

  payload.categories[0].category = 'Salary';
  payload.categories = Array.from({ length: 501 }, (_, index) => ({
    ...payload.categories[0],
    ref: `c${String(index + 1).padStart(3, '0')}`,
  }));
  assert.throws(
    () => assertCategoryOnlyPayload(payload),
    /at most 500 categories/,
  );
});

test('requires a completed target month and at least one category', () => {
  assert.throws(
    () =>
      buildCategoryPayload({
        targetMonth: '2026-07',
        currency: 'AUD',
        budgetMonths: months,
      }),
    /target month is not available/,
  );
});

test('builds locally derived category trends from twenty-four completed months', () => {
  const trendMonths = Array.from({ length: 24 }, (_, index) => {
    const date = new Date(Date.UTC(2024, index, 1)).toISOString().slice(0, 7);
    const actual = 10000 + index * 1000;
    return {
      month: date,
      categoryGroups: [
        {
          id: 'group-never-send',
          name: 'Living costs',
          is_income: false,
          categories: [
            {
              id: 'category-never-send',
              name: 'Groceries',
              budgeted: 15000,
              spent: -actual,
              balance: 15000 - actual,
            },
          ],
        },
      ],
      transactions: [{ payee_name: 'Never send this' }],
    };
  });

  const payload = buildTrendPayload({ currency: 'AUD', budgetMonths: trendMonths });

  assert.equal(payload.analysis_type, 'long_term_category_trends');
  assert.equal(payload.start_month, '2024-01');
  assert.equal(payload.end_month, '2025-12');
  assert.equal(payload.months_in_period, 24);
  assert.deepEqual(payload.categories, [
    {
      ref: 'c001',
      group: 'Living costs',
      category: 'Groceries',
      type: 'expense',
      months_observed: 24,
      active_in_latest_month: true,
      available_evidence: [
        'full_period_average',
        'latest_twelve',
        'observation_coverage',
        'first_vs_latest_six',
        'annualized_trend',
        'variability',
        'budget_frequency',
        'largest_month',
      ],
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
  ]);
  assert.doesNotThrow(() => assertTrendOnlyPayload(payload));

  const serialized = JSON.stringify(payload).toLowerCase();
  for (const forbidden of ['never-send', 'transaction', 'payee', 'account', 'note']) {
    assert.equal(serialized.includes(forbidden), false, forbidden);
  }
});

test('long-term trends include a category that is no longer active', () => {
  const trendMonths = [
    {
      month: '2024-01',
      categoryGroups: [
        {
          name: 'Past costs',
          is_income: false,
          categories: [{ id: 'old-local-id', name: 'Old category', spent: -5000 }],
        },
      ],
    },
    {
      month: '2024-02',
      categoryGroups: [],
    },
  ];

  const payload = buildTrendPayload({ currency: 'AUD', budgetMonths: trendMonths });
  assert.equal(payload.categories[0].active_in_latest_month, false);
  assert.equal(payload.categories[0].months_observed, 1);
  assert.deepEqual(payload.categories[0].available_evidence, [
    'full_period_average',
    'latest_twelve',
    'observation_coverage',
    'largest_month',
  ]);
  assert.equal(JSON.stringify(payload).includes('old-local-id'), false);
});
