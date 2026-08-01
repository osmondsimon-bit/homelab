// Regression tests for the category-only Actual Budget snapshot boundary.
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  assertCategoryOnlyPayload,
  buildCategoryPayload,
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
      target: {
        budgeted_cents: null,
        actual_cents: 410000,
        balance_cents: null,
      },
      comparisons: {
        previous_month_actual_cents: 400000,
        prior_3_month_average_actual_cents: 400000,
        prior_12_month_average_actual_cents: 400000,
        actual_vs_prior_3_month_basis_points: 250,
        budget_variance_cents: null,
      },
    },
    {
      ref: 'c002',
      group: 'Living costs',
      category: 'Groceries',
      type: 'expense',
      months_of_history: 1,
      target: {
        budgeted_cents: 52000,
        actual_cents: 60000,
        balance_cents: -3000,
      },
      comparisons: {
        previous_month_actual_cents: 45000,
        prior_3_month_average_actual_cents: 45000,
        prior_12_month_average_actual_cents: 45000,
        actual_vs_prior_3_month_basis_points: 3333,
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
