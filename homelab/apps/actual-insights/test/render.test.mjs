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
                actual_vs_prior_3_month_basis_points: 2500,
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
});
