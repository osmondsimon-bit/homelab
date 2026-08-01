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
    case 'budget_variance':
      return `Budget variance ${money(comparisons.budget_variance_cents, currency)}`;
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

export function renderPage({ csrf, memos, defaultMonth }) {
  const memoBody = memos[0]
    ? renderMemo(memos[0])
    : '<article><p>No monthly memo has been generated yet.</p></article>';
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Actual monthly insights</title><link rel="stylesheet" href="assets/pico.min.css"><link rel="stylesheet" href="assets/app.css"></head>
<body><main class="container"><header class="page-header"><p class="eyebrow">Actual Budget companion</p><h1>Monthly category insights</h1><p>Manually generated from category totals only. No transactions, payees, accounts, notes, or raw ledger records are sent to the model.</p></header>
<article><form method="post" action="generate"><div class="grid"><label>Completed month<input type="month" name="month" value="${escapeHtml(defaultMonth)}" required></label><div class="submit-wrap"><button type="submit">Generate monthly memo</button></div></div><input type="hidden" name="csrf" value="${escapeHtml(csrf)}"></form></article>
${memoBody}</main></body></html>`;
}
