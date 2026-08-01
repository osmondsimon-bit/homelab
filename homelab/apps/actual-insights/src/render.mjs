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
    case 'annualized_trend':
      return `Annualized direction ${percentage(metrics.annualized_trend_basis_points)}`;
    case 'variability':
      return `Monthly variability ${percentage(metrics.variability_basis_points)} of the category average`;
    case 'budget_frequency':
      return `Over budget in ${metrics.months_over_budget} of ${metrics.months_with_budget} budgeted months`;
    case 'largest_month':
      return `Largest month ${escapeHtml(metrics.largest_month)} at ${money(metrics.largest_month_actual_cents, currency)}`;
    case 'observation_coverage':
      return `Observed in ${category.months_observed} months`;
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

function renderTrendMemo(record) {
  const categories = new Map(record.payload.categories.map(category => [category.ref, category]));
  const findings = record.memo.findings
    .map(finding => renderTrendFinding(finding, categories, record.payload.currency))
    .join('');
  const caveats = record.memo.caveats.map(caveat => `<li>${escapeHtml(caveat)}</li>`).join('');
  return `<section aria-labelledby="trend-heading">
    <header class="memo-header"><p class="eyebrow">Twenty-four-month baseline · ${escapeHtml(record.payload.start_month)} to ${escapeHtml(record.payload.end_month)} · ${escapeHtml(record.model)}</p><h2 id="trend-heading">${escapeHtml(record.memo.headline)}</h2><p>${escapeHtml(record.memo.summary)}</p></header>
    <div class="findings">${findings || '<p>No material long-term category findings were returned.</p>'}</div>
    ${caveats ? `<details><summary>Limits of this baseline</summary><ul>${caveats}</ul></details>` : ''}
  </section>`;
}

export function renderPage({ csrf, memos, defaultMonth }) {
  const monthlyMemo = memos.find(record => !record.kind || record.kind === 'monthly');
  const trendMemo = memos.find(record => record.kind === 'long_term');
  const memoBody = monthlyMemo
    ? renderMemo(monthlyMemo)
    : '<article><p>No monthly memo has been generated yet.</p></article>';
  const trendBody = trendMemo
    ? renderTrendMemo(trendMemo)
    : '<article><p>No long-term category baseline has been generated yet.</p></article>';
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Actual category insights</title><link rel="stylesheet" href="assets/pico.min.css"><link rel="stylesheet" href="assets/app.css"></head>
<body><main class="container"><header class="page-header"><p class="eyebrow">Actual Budget companion</p><h1>Category insights</h1><p>Manually generated from category totals and locally derived trends only. No transactions, payees, accounts, notes, raw monthly series, or ledger records are sent to the model.</p></header>
<article><header><h2>Initial long-term baseline</h2><p>Manually analyze locally derived category trends from the latest twenty-four completed months.</p></header><form method="post" action="generate-trends"><button type="submit">Generate twenty-four-month trend analysis</button><input type="hidden" name="csrf" value="${escapeHtml(csrf)}"></form></article>
${trendBody}
<article><header><h2>Monthly review</h2><p>Generate a completed-month memo with short-term and long-term category comparisons.</p></header><form method="post" action="generate"><div class="grid"><label>Completed month<input type="month" name="month" value="${escapeHtml(defaultMonth)}" required></label><div class="submit-wrap"><button type="submit">Generate monthly memo</button></div></div><input type="hidden" name="csrf" value="${escapeHtml(csrf)}"></form></article>
${memoBody}</main></body></html>`;
}
