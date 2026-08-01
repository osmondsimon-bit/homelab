// Rendering tests prove labels stay data and exact evidence is calculated locally.
import assert from 'node:assert/strict';
import test from 'node:test';

import { renderPage } from '../src/render.mjs';

test('escapes category labels and renders exact local evidence', () => {
  const html = renderPage({
    csrf: 'csrf-token',
    defaultMonth: '2026-06',
    memos: [
      {
        month: '2026-06',
        model: 'gpt-5.6-terra',
        headline: 'Review the highlighted category',
        summary: 'The local evidence shows a material change.',
        payload: {
          currency: 'AUD',
          categories: [
            {
              ref: 'c001',
              group: 'Living <script>alert(1)</script>',
              category: 'Groceries & home',
              target: { budgeted_cents: 50000, actual_cents: 60000, balance_cents: -10000 },
              comparisons: {
                previous_month_actual_cents: 45000,
                prior_3_month_average_actual_cents: 48000,
                prior_12_month_average_actual_cents: 47000,
                prior_24_month_average_actual_cents: 46000,
                actual_vs_prior_3_month_basis_points: 2500,
                actual_vs_prior_24_month_basis_points: 3043,
                budget_variance_cents: -10000,
              },
            },
          ],
        },
        memo: {
          findings: [
            {
              category_ref: 'c001',
              severity: 'watch',
              title: 'Activity moved above its recent pattern',
              observation: 'The category merits review.',
              evidence: ['actual_vs_prior_3_month', 'budget_variance'],
              suggested_review: 'Check the next category allocation.',
            },
          ],
          caveats: [],
        },
      },
    ],
  });

  assert.match(html, /Groceries &amp; home/);
  assert.match(html, /Living &lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>alert/);
  assert.match(html, /Actual \$600\.00/);
  assert.match(html, /prior three-month average \$480\.00/);
  assert.match(html, /change 25\.0%/);
  assert.match(html, /Budget variance -\$100\.00/);
  assert.match(html, /Generate twenty-four-month trend analysis/);
  assert.match(html, /href="\/insights\/assets\/pico\.min\.css"/);
  assert.match(html, /action="\/insights\/generate-trends"/);
  assert.match(html, /action="\/insights\/generate"/);
});

test('renders long-term model prose with exact trend evidence calculated locally', () => {
  const html = renderPage({
    csrf: 'csrf-token',
    defaultMonth: '2026-06',
    memos: [
      {
        kind: 'long_term',
        month: '2025-12',
        model: 'gpt-5.6-terra',
        payload: {
          start_month: '2024-01',
          end_month: '2025-12',
          months_in_period: 24,
          currency: 'AUD',
          categories: [
            {
              ref: 'c001',
              group: 'Living costs',
              category: 'Groceries',
              months_observed: 24,
              metrics: {
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
        },
        memo: {
          headline: 'A long-term category pattern merits review',
          summary: 'The available history shows sustained pressure.',
          findings: [
            {
              category_ref: 'c001',
              severity: 'watch',
              pattern: 'rising',
              title: 'The category has moved upward',
              observation: 'Recent activity is above the opening period.',
              evidence: ['first_vs_latest_six', 'annualized_trend', 'budget_frequency'],
              suggested_review: 'Review whether its long-term allocation still fits.',
            },
          ],
          caveats: [],
        },
      },
    ],
  });

  assert.match(html, /Twenty-four-month baseline/);
  assert.match(html, /Opening six-month average \$125\.00/);
  assert.match(html, /latest six-month average \$305\.00/);
  assert.match(html, /Annualized direction 55\.8%/);
  assert.match(html, /Over budget in 18 of 24 positively budgeted months/);
});

test('renders a spend dashboard with underlying and exceptional category metrics', () => {
  const html = renderPage({
    csrf: 'csrf-token',
    defaultMonth: '2026-06',
    categorySort: 'deviation',
    memos: [
      {
        kind: 'long_term',
        model: 'gpt-5.6-terra',
        payload: {
          schema_version: 2,
          analysis_mode: 'spend_only',
          start_month: '2024-07',
          end_month: '2026-06',
          currency: 'AUD',
          spend_summary: {
            latest_12_total_actual_cents: 8000000,
            previous_12_total_actual_cents: 7000000,
            latest_12_underlying_actual_cents: 5000000,
            previous_12_underlying_actual_cents: 4500000,
            latest_12_average_monthly_underlying_cents: 416667,
            latest_12_median_monthly_underlying_cents: 400000,
            latest_12_standard_deviation_monthly_underlying_cents: 50000,
            latest_12_vs_previous_12_underlying_basis_points: 1111,
            latest_12_exceptional_actual_cents: 3000000,
          },
          categories: [
            {
              ref: 'c001', group: 'Lifestyle', category: 'Holidays', type: 'expense',
              is_exceptional: false, months_observed: 24,
              metrics: {
                latest_12_total_actual_cents: 1200000,
                previous_12_total_actual_cents: 600000,
                latest_12_month_average_actual_cents: 100000,
                latest_12_active_month_average_actual_cents: 400000,
                latest_12_median_actual_cents: 0,
                latest_12_standard_deviation_cents: 173205,
                latest_12_active_months: 3,
                latest_12_vs_previous_12_basis_points: 10000,
              },
            },
            {
              ref: 'c002', group: 'Exceptional', category: 'House Build', type: 'expense',
              is_exceptional: true, months_observed: 24,
              metrics: {
                latest_12_total_actual_cents: 3000000,
                previous_12_total_actual_cents: 2500000,
                latest_12_month_average_actual_cents: 250000,
                latest_12_active_month_average_actual_cents: 3000000,
                latest_12_median_actual_cents: 0,
                latest_12_standard_deviation_cents: 829156,
                latest_12_active_months: 1,
                latest_12_vs_previous_12_basis_points: 2000,
              },
            },
          ],
        },
        memo: { headline: 'Underlying spend is measurable', summary: 'Exceptional costs are separated.', findings: [], caveats: [] },
      },
      { kind: 'long_term', payload: { schema_version: 1 } },
    ],
  });

  assert.doesNotMatch(html, /over budget/i);
  assert.match(html, /Spend dashboard/);
  assert.match(html, /Underlying spend/);
  assert.match(html, /\$50,000\.00/);
  assert.match(html, /Exceptional spend/);
  assert.match(html, /\$30,000\.00/);
  assert.match(html, /Holidays/);
  assert.match(html, /\$12,000\.00/);
  assert.match(html, /\$4,000\.00/);
  assert.match(html, /House Build/);
  assert.match(html, /Excluded from underlying run rate/);
  assert.match(html, /Supersedes 1 earlier baseline/);
  assert.match(html, /sort=deviation/);
  assert.ok(html.indexOf('House Build') < html.indexOf('Holidays'));
});
