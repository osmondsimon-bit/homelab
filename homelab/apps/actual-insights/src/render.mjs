// Renders model prose with category names and exact monetary evidence rehydrated only on the VM.

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function money(cents, currency) {
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency,
  }).format(cents / 100);
}

function percentage(basisPoints) {
  return `${(basisPoints / 100).toFixed(1)}%`;
}

function evidenceText(category, evidence, currency) {
  const { target, comparisons } = category;
  switch (evidence) {
    case 'target_actual':
      return `Actual ${money(target.actual_cents, currency)}`;
    case 'target_budgeted':
      return `Budgeted ${money(target.budgeted_cents, currency)}`;
    case 'target_balance':
      return `Balance ${money(target.balance_cents, currency)}`;
    case 'previous_month_actual':
      return `Previous month ${money(comparisons.previous_month_actual_cents, currency)}`;
    case 'actual_vs_prior_3_month':
      return `Actual ${money(target.actual_cents, currency)} · prior three-month average ${money(comparisons.prior_3_month_average_actual_cents, currency)} · change ${percentage(comparisons.actual_vs_prior_3_month_basis_points)}`;
    case 'actual_vs_prior_12_month':
      return `Actual ${money(target.actual_cents, currency)} · prior twelve-month average ${money(comparisons.prior_12_month_average_actual_cents, currency)}`;
    case 'actual_vs_prior_24_month':
      return `Actual ${money(target.actual_cents, currency)} · prior twenty-four-month average ${money(comparisons.prior_24_month_average_actual_cents, currency)} · change ${percentage(comparisons.actual_vs_prior_24_month_basis_points)}`;
    case 'budget_variance':
      return `Budget variance ${money(comparisons.budget_variance_cents, currency)}`;
    default:
      return 'Evidence unavailable';
  }
}

function trendEvidenceText(category, evidence, currency) {
  const { metrics } = category;
  switch (evidence) {
    case 'full_period_average':
      return `Full-period monthly average ${money(metrics.full_period_average_actual_cents, currency)}`;
    case 'first_vs_latest_six':
      return `Opening six-month average ${money(metrics.first_6_month_average_actual_cents, currency)} · latest six-month average ${money(metrics.latest_6_month_average_actual_cents, currency)} · change ${percentage(metrics.latest_6_vs_first_6_basis_points)}`;
    case 'latest_twelve':
      return `Latest twelve-month average ${money(metrics.latest_12_month_average_actual_cents, currency)}`;
    case 'latest_twelve_total':
      return `Latest twelve-month total ${money(metrics.latest_12_total_actual_cents, currency)}`;
    case 'previous_twelve_total':
      return `Previous twelve-month total ${money(metrics.previous_12_total_actual_cents, currency)}`;
    case 'latest_vs_previous_twelve':
      return `Latest twelve-month change ${percentage(metrics.latest_12_vs_previous_12_basis_points)}`;
    case 'monthly_median':
      return `Latest twelve-month median ${money(metrics.latest_12_median_actual_cents, currency)}`;
    case 'monthly_deviation':
      return `Latest twelve-month standard deviation ${money(metrics.latest_12_standard_deviation_cents, currency)}`;
    case 'active_month_average':
      return `Active-month average ${money(metrics.latest_12_active_month_average_actual_cents, currency)} across ${metrics.latest_12_active_months} active months`;
    case 'annualized_trend':
      return `Annualized direction ${percentage(metrics.annualized_trend_basis_points)}`;
    case 'variability':
      return `Monthly variability ${percentage(metrics.variability_basis_points)} of the category average`;
    case 'budget_frequency':
      return `Over budget in ${metrics.months_over_positive_budget ?? metrics.months_over_budget} of ${metrics.months_with_positive_budget ?? metrics.months_with_budget} positively budgeted months`;
    case 'largest_month':
      return `Largest month ${escapeHtml(metrics.largest_month)} at ${money(metrics.largest_month_actual_cents, currency)}`;
    case 'observation_coverage':
      return `Observed in ${category.months_observed} months`;
    case 'exceptional_status':
      return 'Configured as exceptional and excluded from the underlying run rate';
    default:
      return 'Evidence unavailable';
  }
}

function renderFinding(finding, categories, currency) {
  const category = categories.get(finding.category_ref);
  const evidence = finding.evidence
    .map(item => `<li>${escapeHtml(evidenceText(category, item, currency))}</li>`)
    .join('');
  return `<article class="finding severity-${escapeHtml(finding.severity)}">
    <header><p class="eyebrow">${escapeHtml(category.group)} / ${escapeHtml(category.category)}</p><h3>${escapeHtml(finding.title)}</h3></header>
    <p>${escapeHtml(finding.observation)}</p><ul class="evidence">${evidence}</ul>
    <footer><strong>Review:</strong> ${escapeHtml(finding.suggested_review)}</footer>
  </article>`;
}

function renderMemo(record) {
  const categories = new Map(record.payload.categories.map(category => [category.ref, category]));
  const findings = record.memo.findings
    .map(finding => renderFinding(finding, categories, record.payload.currency))
    .join('');
  const caveats = record.memo.caveats.map(caveat => `<li>${escapeHtml(caveat)}</li>`).join('');
  return `<section aria-labelledby="memo-heading">
    <header class="memo-header"><p class="eyebrow">${escapeHtml(record.month)} · ${escapeHtml(record.model)}</p><h2 id="memo-heading">${escapeHtml(record.headline)}</h2><p>${escapeHtml(record.summary)}</p></header>
    <div class="findings">${findings || '<p>No material category findings were returned.</p>'}</div>
    ${caveats ? `<details><summary>Limits of this memo</summary><ul>${caveats}</ul></details>` : ''}
  </section>`;
}

function renderTrendFinding(finding, categories, currency) {
  const category = categories.get(finding.category_ref);
  const evidence = finding.evidence
    .map(item => `<li>${escapeHtml(trendEvidenceText(category, item, currency))}</li>`)
    .join('');
  return `<article class="finding severity-${escapeHtml(finding.severity)}">
    <header><p class="eyebrow">${escapeHtml(category.group)} / ${escapeHtml(category.category)} · ${escapeHtml(finding.pattern.replaceAll('_', ' '))}</p><h3>${escapeHtml(finding.title)}</h3></header>
    <p>${escapeHtml(finding.observation)}</p><ul class="evidence">${evidence}</ul>
    <footer><strong>Review:</strong> ${escapeHtml(finding.suggested_review)}</footer>
  </article>`;
}

function comparison(value) {
  return value === null || value === undefined ? 'Not available' : percentage(value);
}

function sortExpenseCategories(categories, categorySort) {
  const rows = categories.filter(category => category.type === 'expense');
  const numericField = {
    latest12: 'latest_12_total_actual_cents',
    average: 'latest_12_month_average_actual_cents',
    change: 'latest_12_vs_previous_12_basis_points',
    deviation: 'latest_12_standard_deviation_cents',
  }[categorySort];
  return [...rows].sort((left, right) => {
    if (categorySort === 'category') {
      return left.category.localeCompare(right.category) || left.group.localeCompare(right.group);
    }
    const leftValue = left.metrics[numericField || 'latest_12_total_actual_cents'];
    const rightValue = right.metrics[numericField || 'latest_12_total_actual_cents'];
    if (leftValue === null || leftValue === undefined) return 1;
    if (rightValue === null || rightValue === undefined) return -1;
    return rightValue - leftValue || left.category.localeCompare(right.category);
  });
}

function renderSpendDashboard(record, categorySort) {
  const { currency, spend_summary: summary } = record.payload;
  const categories = sortExpenseCategories(record.payload.categories, categorySort);
  const rows = categories.map(category => {
    const metrics = category.metrics;
    const exceptional = category.is_exceptional
      ? '<span class="category-flag">Excluded from underlying run rate</span>'
      : '';
    return `<tr><th scope="row">${escapeHtml(category.category)}<small>${escapeHtml(category.group)}</small>${exceptional}</th>
      <td>${money(metrics.latest_12_total_actual_cents, currency)}</td>
      <td>${metrics.previous_12_total_actual_cents === null ? '—' : money(metrics.previous_12_total_actual_cents, currency)}</td>
      <td>${money(metrics.latest_12_month_average_actual_cents, currency)}</td>
      <td>${metrics.latest_12_active_month_average_actual_cents === null ? '—' : money(metrics.latest_12_active_month_average_actual_cents, currency)}</td>
      <td>${money(metrics.latest_12_median_actual_cents, currency)}</td>
      <td>${money(metrics.latest_12_standard_deviation_cents, currency)}</td>
      <td>${metrics.latest_12_active_months}</td>
      <td>${comparison(metrics.latest_12_vs_previous_12_basis_points)}</td></tr>`;
  }).join('');
  return `<section aria-labelledby="dashboard-heading"><header class="memo-header"><p class="eyebrow">Deterministic local calculations</p><h2 id="dashboard-heading">Spend dashboard</h2><p>Latest twelve completed months. Underlying spend excludes configured exceptional categories; total spend still includes them.</p></header>
    <div class="metric-grid">
      <article><small>Total spend</small><strong>${money(summary.latest_12_total_actual_cents, currency)}</strong></article>
      <article><small>Underlying spend</small><strong>${money(summary.latest_12_underlying_actual_cents, currency)}</strong></article>
      <article><small>Underlying monthly average</small><strong>${money(summary.latest_12_average_monthly_underlying_cents, currency)}</strong></article>
      <article><small>Underlying median month</small><strong>${money(summary.latest_12_median_monthly_underlying_cents, currency)}</strong></article>
      <article><small>Underlying monthly deviation</small><strong>${money(summary.latest_12_standard_deviation_monthly_underlying_cents, currency)}</strong></article>
      <article><small>Underlying annual change</small><strong>${comparison(summary.latest_12_vs_previous_12_underlying_basis_points)}</strong></article>
      <article><small>Exceptional spend</small><strong>${money(summary.latest_12_exceptional_actual_cents, currency)}</strong></article>
    </div>
    <div class="table-wrap"><table><caption>Expense category statistics for the latest twelve completed months</caption><thead><tr>
      <th scope="col"><a href="/insights/?sort=category">Category</a></th>
      <th scope="col"><a href="/insights/?sort=latest12">Latest total</a></th>
      <th scope="col">Previous total</th>
      <th scope="col"><a href="/insights/?sort=average">Monthly average</a></th>
      <th scope="col">Active-month average</th><th scope="col">Median</th>
      <th scope="col"><a href="/insights/?sort=deviation">Deviation</a></th>
      <th scope="col">Active months</th><th scope="col"><a href="/insights/?sort=change">Change</a></th>
    </tr></thead><tbody>${rows}</tbody></table></div></section>`;
}

function renderTrendMemo(record, { earlierBaselines = 0, categorySort = 'latest12' } = {}) {
  const categories = new Map(record.payload.categories.map(category => [category.ref, category]));
  const findings = record.memo.findings
    .map(finding => renderTrendFinding(finding, categories, record.payload.currency))
    .join('');
  const caveats = record.memo.caveats.map(caveat => `<li>${escapeHtml(caveat)}</li>`).join('');
  const isSpendV2 = record.payload.schema_version === 2;
  const baselineLabel = isSpendV2
    ? 'Twenty-four-month spend baseline'
    : 'Twenty-four-month baseline · Legacy budget-oriented';
  const superseded = earlierBaselines > 0
    ? `<p class="baseline-note">Supersedes ${earlierBaselines} earlier baseline${earlierBaselines === 1 ? '' : 's'}.</p>`
    : '';
  const dashboard = isSpendV2 ? renderSpendDashboard(record, categorySort) : '';
  return `${dashboard}<section aria-labelledby="trend-heading">
    <header class="memo-header"><p class="eyebrow">${baselineLabel} · ${escapeHtml(record.payload.start_month)} to ${escapeHtml(record.payload.end_month)} · ${escapeHtml(record.model)}</p>${superseded}<h2 id="trend-heading">${escapeHtml(record.memo.headline)}</h2><p>${escapeHtml(record.memo.summary)}</p></header>
    <div class="findings">${findings || '<p>No material long-term category findings were returned.</p>'}</div>
    ${caveats ? `<details><summary>Limits of this baseline</summary><ul>${caveats}</ul></details>` : ''}
  </section>`;
}

export function renderPage({ csrf, memos, defaultMonth, categorySort = 'latest12' }) {
  const monthlyMemo = memos.find(record => !record.kind || record.kind === 'monthly');
  const trendMemos = memos.filter(record => record.kind === 'long_term');
  const trendMemo = trendMemos[0];
  const memoBody = monthlyMemo
    ? renderMemo(monthlyMemo)
    : '<article><p>No monthly memo has been generated yet.</p></article>';
  const trendBody = trendMemo
    ? renderTrendMemo(trendMemo, {
      earlierBaselines: trendMemos.length - 1,
      categorySort,
    })
    : '<article><p>No long-term category baseline has been generated yet.</p></article>';
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Actual category insights</title><link rel="stylesheet" href="/insights/assets/pico.min.css"><link rel="stylesheet" href="/insights/assets/app.css"></head>
<body><main class="container"><header class="page-header"><p class="eyebrow">Actual Budget companion</p><h1>Category insights</h1><p>Manually generated from category totals and locally derived trends only. No transactions, payees, accounts, notes, raw monthly series, or ledger records are sent to the model.</p></header>
<article><header><h2>Initial long-term baseline</h2><p>Manually analyze locally derived category trends from the latest twenty-four completed months.</p></header><form method="post" action="/insights/generate-trends"><button type="submit">Generate twenty-four-month trend analysis</button><input type="hidden" name="csrf" value="${escapeHtml(csrf)}"></form></article>
${trendBody}
<article><header><h2>Monthly review</h2><p>Generate a completed-month memo with short-term and long-term category comparisons.</p></header><form method="post" action="/insights/generate"><div class="grid"><label>Completed month<input type="month" name="month" value="${escapeHtml(defaultMonth)}" required></label><div class="submit-wrap"><button type="submit">Generate monthly memo</button></div></div><input type="hidden" name="csrf" value="${escapeHtml(csrf)}"></form></article>
${memoBody}</main></body></html>`;
}
