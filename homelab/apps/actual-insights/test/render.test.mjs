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
  assert.match(html, /Over budget in 18 of 24 budgeted months/);
});
