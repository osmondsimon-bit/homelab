// Converts Actual's budget-month objects into the only data shape permitted to cross the LLM boundary.

const rootFields = new Set([
  'schema_version',
  'analysis_mode',
  'target_month',
  'currency',
  'categories',
]);
const categoryFields = new Set([
  'ref',
  'group',
  'category',
  'type',
  'months_of_history',
  'available_evidence',
  'target',
  'comparisons',
]);
const targetFields = new Set(['budgeted_cents', 'actual_cents', 'balance_cents']);
const comparisonFields = new Set([
  'previous_month_actual_cents',
  'prior_3_month_average_actual_cents',
  'prior_12_month_average_actual_cents',
  'prior_24_month_average_actual_cents',
  'actual_vs_prior_3_month_basis_points',
  'actual_vs_prior_24_month_basis_points',
  'budget_variance_cents',
]);
const trendRootFields = new Set([
  'schema_version',
  'analysis_type',
  'analysis_mode',
  'start_month',
  'end_month',
  'currency',
  'months_in_period',
  'spend_summary',
  'categories',
]);
const spendSummaryFields = new Set([
  'latest_12_total_actual_cents',
  'previous_12_total_actual_cents',
  'latest_12_underlying_actual_cents',
  'previous_12_underlying_actual_cents',
  'latest_12_average_monthly_underlying_cents',
  'latest_12_median_monthly_underlying_cents',
  'latest_12_standard_deviation_monthly_underlying_cents',
  'latest_12_vs_previous_12_underlying_basis_points',
  'latest_12_exceptional_actual_cents',
]);
const trendCategoryFields = new Set([
  'ref',
  'group',
  'category',
  'type',
  'months_observed',
  'active_in_latest_month',
  'is_exceptional',
  'available_evidence',
  'metrics',
]);
const monthlyEvidenceTypes = new Set([
  'target_actual',
  'target_budgeted',
  'target_balance',
  'previous_month_actual',
  'actual_vs_prior_3_month',
  'actual_vs_prior_12_month',
  'actual_vs_prior_24_month',
  'budget_variance',
]);
const trendEvidenceTypes = new Set([
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
  'exceptional_status',
]);
const trendMetricFields = new Set([
  'total_actual_cents',
  'full_period_average_actual_cents',
  'first_6_month_average_actual_cents',
  'latest_6_month_average_actual_cents',
  'latest_12_month_average_actual_cents',
  'latest_12_total_actual_cents',
  'previous_12_total_actual_cents',
  'previous_12_month_average_actual_cents',
  'latest_12_median_actual_cents',
  'latest_12_standard_deviation_cents',
  'latest_12_active_month_average_actual_cents',
  'latest_12_active_months',
  'latest_12_vs_previous_12_basis_points',
  'latest_6_vs_first_6_basis_points',
  'annualized_trend_basis_points',
  'variability_basis_points',
  'months_with_positive_budget',
  'months_over_positive_budget',
  'largest_month_actual_cents',
  'largest_month',
]);

function assertExactFields(value, allowed, location) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError(`${location} must be an object`);
  }
  for (const field of Object.keys(value)) {
    if (!allowed.has(field)) {
      throw new Error(`category-only payload contains unexpected field: ${field}`);
    }
  }
  for (const field of allowed) {
    if (!(field in value)) {
      throw new Error(`category-only payload is missing field: ${location}.${field}`);
    }
  }
}

function integerOrNull(value, location) {
  if (value === null) {
    return;
  }
  if (!Number.isSafeInteger(value)) {
    throw new TypeError(`${location} must be an integer number of cents or null`);
  }
}

function assertCategoryLabel(category) {
  if (
    typeof category.group !== 'string' ||
    typeof category.category !== 'string' ||
    category.group.length < 1 ||
    category.group.length > 200 ||
    category.category.length < 1 ||
    category.category.length > 200
  ) {
    throw new TypeError('category labels must contain between one and 200 characters');
  }
  if (!['expense', 'income'].includes(category.type)) {
    throw new Error('category type must be expense or income');
  }
}

function assertEvidenceList(value, allowed, location) {
  if (!Array.isArray(value) || value.length === 0 || new Set(value).size !== value.length) {
    throw new Error(`${location} must be a non-empty unique evidence list`);
  }
  for (const evidence of value) {
    if (!allowed.has(evidence)) {
      throw new Error(`${location} contains unsupported evidence`);
    }
  }
}

export function assertCategoryOnlyPayload(payload) {
  assertExactFields(payload, rootFields, 'payload');
  if (payload.schema_version !== 2) {
    throw new Error('unsupported category payload schema version');
  }
  if (!['spend_only', 'budget_and_spend'].includes(payload.analysis_mode)) {
    throw new Error('unsupported monthly analysis mode');
  }
  if (!/^\d{4}-\d{2}$/.test(payload.target_month)) {
    throw new Error('target_month must use YYYY-MM');
  }
  if (!/^[A-Z]{3}$/.test(payload.currency)) {
    throw new Error('currency must be a three-letter uppercase code');
  }
  if (!Array.isArray(payload.categories) || payload.categories.length === 0) {
    throw new Error('category-only payload requires at least one category');
  }
  if (payload.categories.length > 500) {
    throw new Error('category-only payload permits at most 500 categories');
  }

  const refs = new Set();
  for (const [index, category] of payload.categories.entries()) {
    assertExactFields(category, categoryFields, `categories[${index}]`);
    assertExactFields(category.target, targetFields, `categories[${index}].target`);
    assertExactFields(
      category.comparisons,
      comparisonFields,
      `categories[${index}].comparisons`,
    );
    if (!/^c\d{3,}$/.test(category.ref) || refs.has(category.ref)) {
      throw new Error('category refs must be unique local references');
    }
    refs.add(category.ref);
    assertCategoryLabel(category);
    assertEvidenceList(
      category.available_evidence,
      monthlyEvidenceTypes,
      `${category.ref}.available_evidence`,
    );
    if (!Number.isSafeInteger(category.months_of_history) || category.months_of_history < 0) {
      throw new TypeError('months_of_history must be a non-negative integer');
    }
    for (const [field, value] of Object.entries(category.target)) {
      integerOrNull(value, `${category.ref}.target.${field}`);
    }
    for (const [field, value] of Object.entries(category.comparisons)) {
      integerOrNull(value, `${category.ref}.comparisons.${field}`);
    }
  }
  return payload;
}

export function assertTrendOnlyPayload(payload) {
  assertExactFields(payload, trendRootFields, 'trend payload');
  if (payload.schema_version !== 2 || payload.analysis_type !== 'long_term_category_trends') {
    throw new Error('unsupported long-term category payload contract');
  }
  if (!['spend_only', 'budget_and_spend'].includes(payload.analysis_mode)) {
    throw new Error('unsupported long-term analysis mode');
  }
  if (!/^\d{4}-\d{2}$/.test(payload.start_month) || !/^\d{4}-\d{2}$/.test(payload.end_month)) {
    throw new Error('trend period months must use YYYY-MM');
  }
  if (!/^[A-Z]{3}$/.test(payload.currency)) {
    throw new Error('currency must be a three-letter uppercase code');
  }
  if (
    !Number.isSafeInteger(payload.months_in_period) ||
    payload.months_in_period < 1 ||
    payload.months_in_period > 24
  ) {
    throw new Error('trend payload requires between one and twenty-four months');
  }
  if (!Array.isArray(payload.categories) || payload.categories.length === 0) {
    throw new Error('trend payload requires at least one category');
  }
  if (payload.categories.length > 500) {
    throw new Error('trend payload permits at most 500 categories');
  }
  assertExactFields(payload.spend_summary, spendSummaryFields, 'trend spend summary');
  for (const [field, value] of Object.entries(payload.spend_summary)) {
    integerOrNull(value, `trend spend summary.${field}`);
  }

  const refs = new Set();
  for (const [index, category] of payload.categories.entries()) {
    assertExactFields(category, trendCategoryFields, `trend categories[${index}]`);
    assertExactFields(category.metrics, trendMetricFields, `trend categories[${index}].metrics`);
    if (!/^c\d{3,}$/.test(category.ref) || refs.has(category.ref)) {
      throw new Error('trend category refs must be unique local references');
    }
    refs.add(category.ref);
    assertCategoryLabel(category);
    assertEvidenceList(
      category.available_evidence,
      trendEvidenceTypes,
      `${category.ref}.available_evidence`,
    );
    if (
      !Number.isSafeInteger(category.months_observed) ||
      category.months_observed < 1 ||
      category.months_observed > payload.months_in_period
    ) {
      throw new Error('months_observed is outside the trend period');
    }
    if (typeof category.active_in_latest_month !== 'boolean') {
      throw new TypeError('active_in_latest_month must be boolean');
    }
    if (typeof category.is_exceptional !== 'boolean') {
      throw new TypeError('is_exceptional must be boolean');
    }
    for (const [field, value] of Object.entries(category.metrics)) {
      if (field === 'largest_month') {
        if (value !== null && !/^\d{4}-\d{2}$/.test(value)) {
          throw new Error('largest_month must use YYYY-MM or null');
        }
      } else {
        integerOrNull(value, `${category.ref}.metrics.${field}`);
      }
    }
  }
  return payload;
}

function categoryKey(group, category) {
  return category.id || `${group.name}\u0000${category.name}`;
}

function actualAmount(group, category) {
  if (group.is_income) {
    return Number.isSafeInteger(category.received) ? category.received : 0;
  }
  return Number.isSafeInteger(category.spent) ? -category.spent : 0;
}

function nullableInteger(value) {
  return Number.isSafeInteger(value) ? value : null;
}

function average(values, count) {
  const selected = values.slice(-count);
  if (selected.length === 0) {
    return null;
  }
  return Math.round(selected.reduce((sum, value) => sum + value, 0) / selected.length);
}

function basisPoints(target, baseline) {
  if (baseline === null || baseline === 0) {
    return null;
  }
  return Math.round(((target - baseline) / Math.abs(baseline)) * 10000);
}

function flattenMonth(budgetMonth) {
  const categories = new Map();
  for (const group of budgetMonth.categoryGroups || []) {
    for (const category of group.categories || []) {
      categories.set(categoryKey(group, category), {
        group: String(group.name || ''),
        category: String(category.name || ''),
        type: group.is_income ? 'income' : 'expense',
        budgeted: nullableInteger(category.budgeted),
        actual: actualAmount(group, category),
        balance: nullableInteger(category.balance),
      });
    }
  }
  return categories;
}

function availableMonthlyEvidence(row) {
  const evidence = ['target_actual'];
  if (row.budgeted !== null) evidence.push('target_budgeted');
  if (row.balance !== null) evidence.push('target_balance');
  if (row.previous_month_actual_cents !== null) evidence.push('previous_month_actual');
  if (row.actual_vs_prior_3_month_basis_points !== null) {
    evidence.push('actual_vs_prior_3_month');
  }
  if (row.prior_12_month_average_actual_cents !== null) {
    evidence.push('actual_vs_prior_12_month');
  }
  if (row.prior_24_month_average_actual_cents !== null) {
    evidence.push('actual_vs_prior_24_month');
  }
  if (row.budget_variance_cents !== null) evidence.push('budget_variance');
  return evidence;
}

export function buildCategoryPayload({ targetMonth, currency, budgetMonths }) {
  if (!/^\d{4}-\d{2}$/.test(targetMonth)) {
    throw new Error('target month must use YYYY-MM');
  }
  const ordered = [...budgetMonths]
    .filter(month => month && /^\d{4}-\d{2}$/.test(month.month))
    .sort((left, right) => left.month.localeCompare(right.month));
  const targetIndex = ordered.findIndex(month => month.month === targetMonth);
  if (targetIndex === -1) {
    throw new Error('target month is not available in Actual');
  }

  const targetCategories = flattenMonth(ordered[targetIndex]);
  const history = ordered.slice(Math.max(0, targetIndex - 24), targetIndex).map(flattenMonth);
  const rows = [];
  for (const [key, target] of targetCategories) {
    const positiveBudget = target.budgeted !== null && target.budgeted > 0
      ? target.budgeted
      : null;
    const priorActuals = history
      .map(month => month.get(key))
      .filter(Boolean)
      .map(category => category.actual);
    const prior3 = average(priorActuals, 3);
    const prior12 = average(priorActuals, 12);
    const prior24 = average(priorActuals, 24);
    rows.push({
      ...target,
      budgeted: positiveBudget,
      balance: positiveBudget === null ? null : target.balance,
      months_of_history: priorActuals.length,
      previous_month_actual_cents: priorActuals.at(-1) ?? null,
      prior_3_month_average_actual_cents: prior3,
      prior_12_month_average_actual_cents: prior12,
      prior_24_month_average_actual_cents: prior24,
      actual_vs_prior_3_month_basis_points: basisPoints(target.actual, prior3),
      actual_vs_prior_24_month_basis_points: basisPoints(target.actual, prior24),
      budget_variance_cents:
        positiveBudget === null ? null : positiveBudget - target.actual,
    });
  }
  rows.sort(
    (left, right) =>
      left.group.localeCompare(right.group) || left.category.localeCompare(right.category),
  );

  const payload = {
    schema_version: 2,
    analysis_mode: rows.some(row => row.type === 'expense' && row.budgeted !== null)
      ? 'budget_and_spend'
      : 'spend_only',
    target_month: targetMonth,
    currency: String(currency || '').toUpperCase(),
    categories: rows.map((row, index) => ({
      ref: `c${String(index + 1).padStart(3, '0')}`,
      group: row.group,
      category: row.category,
      type: row.type,
      months_of_history: row.months_of_history,
      available_evidence: availableMonthlyEvidence(row),
      target: {
        budgeted_cents: row.budgeted,
        actual_cents: row.actual,
        balance_cents: row.balance,
      },
      comparisons: {
        previous_month_actual_cents: row.previous_month_actual_cents,
        prior_3_month_average_actual_cents: row.prior_3_month_average_actual_cents,
        prior_12_month_average_actual_cents: row.prior_12_month_average_actual_cents,
        prior_24_month_average_actual_cents: row.prior_24_month_average_actual_cents,
        actual_vs_prior_3_month_basis_points:
          row.actual_vs_prior_3_month_basis_points,
        actual_vs_prior_24_month_basis_points:
          row.actual_vs_prior_24_month_basis_points,
        budget_variance_cents: row.budget_variance_cents,
      },
    })),
  };
  return assertCategoryOnlyPayload(payload);
}

function populationVariabilityBasisPoints(values, mean) {
  if (values.length < 2 || mean === 0) {
    return null;
  }
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
  return Math.round((Math.sqrt(variance) / Math.abs(mean)) * 10000);
}

function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}

function median(values) {
  if (values.length === 0) return null;
  const ordered = [...values].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  if (ordered.length % 2 === 1) return ordered[middle];
  return Math.round((ordered[middle - 1] + ordered[middle]) / 2);
}

function populationStandardDeviation(values) {
  if (values.length === 0) return null;
  const mean = sum(values) / values.length;
  const variance = values.reduce((total, value) => total + (value - mean) ** 2, 0)
    / values.length;
  return Math.round(Math.sqrt(variance));
}

function annualizedTrendBasisPoints(points, mean) {
  if (points.length < 2 || mean === 0) {
    return null;
  }
  const xMean = points.reduce((sum, point) => sum + point.index, 0) / points.length;
  const yMean = points.reduce((sum, point) => sum + point.actual, 0) / points.length;
  const numerator = points.reduce(
    (sum, point) => sum + (point.index - xMean) * (point.actual - yMean),
    0,
  );
  const denominator = points.reduce(
    (sum, point) => sum + (point.index - xMean) ** 2,
    0,
  );
  if (denominator === 0) {
    return null;
  }
  return Math.round((((numerator / denominator) * 12) / Math.abs(mean)) * 10000);
}

function availableTrendEvidence(metrics, monthsObserved) {
  const evidence = [
    'full_period_average',
    'latest_twelve',
    'latest_twelve_total',
    'monthly_median',
    'monthly_deviation',
    'observation_coverage',
  ];
  if (metrics.latest_12_active_months > 0) evidence.push('active_month_average');
  if (metrics.previous_12_total_actual_cents !== null) evidence.push('previous_twelve_total');
  if (metrics.latest_12_vs_previous_12_basis_points !== null) {
    evidence.push('latest_vs_previous_twelve');
  }
  if (monthsObserved >= 12 && metrics.latest_6_vs_first_6_basis_points !== null) {
    evidence.push('first_vs_latest_six');
  }
  if (metrics.annualized_trend_basis_points !== null) evidence.push('annualized_trend');
  if (metrics.variability_basis_points !== null) evidence.push('variability');
  if (metrics.months_with_positive_budget > 0) evidence.push('budget_frequency');
  if (metrics.largest_month_actual_cents !== null) evidence.push('largest_month');
  return evidence;
}

export function buildTrendPayload({ currency, budgetMonths, exceptionalCategories = [] }) {
  const ordered = [...budgetMonths]
    .filter(month => month && /^\d{4}-\d{2}$/.test(month.month))
    .sort((left, right) => left.month.localeCompare(right.month))
    .slice(-24);
  if (ordered.length === 0) {
    throw new Error('long-term analysis requires completed budget months');
  }

  const flattened = ordered.map(flattenMonth);
  const exceptionalNames = new Set(exceptionalCategories);
  const records = new Map();
  for (const [monthIndex, month] of flattened.entries()) {
    for (const [key, category] of month) {
      const record = records.get(key) || { observedMonths: 0 };
      record.group = category.group;
      record.category = category.category;
      record.type = category.type;
      record.observedMonths += 1;
      records.set(key, record);
    }
  }

  const rows = [...records.entries()].map(([key, record]) => {
    const points = flattened.map((month, index) => {
      const category = month.get(key);
      return {
        index,
        month: ordered[index].month,
        actual: category?.actual ?? 0,
        budgeted: category?.budgeted ?? null,
      };
    });
    const actuals = points.map(point => point.actual);
    const fullAverage = average(actuals, actuals.length);
    const first6 = average(actuals.slice(0, 6), 6);
    const latest6 = average(actuals, 6);
    const latest12 = actuals.slice(-12);
    const previous12 = actuals.length > 12 ? actuals.slice(-24, -12) : [];
    const activeLatest12 = latest12.filter(value => value !== 0);
    const budgetPoints = points.filter(point => point.budgeted !== null && point.budgeted > 0);
    const largest = points.reduce(
      (selected, point) => (selected === null || point.actual > selected.actual ? point : selected),
      null,
    );
    return {
      key,
      ...record,
      points,
      is_exceptional: record.type === 'expense' && exceptionalNames.has(record.category),
      active_in_latest_month: flattened.at(-1).has(key),
      metrics: {
        total_actual_cents: actuals.reduce((sum, value) => sum + value, 0),
        full_period_average_actual_cents: fullAverage,
        first_6_month_average_actual_cents: first6,
        latest_6_month_average_actual_cents: latest6,
        latest_12_month_average_actual_cents: average(actuals, 12),
        latest_12_total_actual_cents: sum(latest12),
        previous_12_total_actual_cents: previous12.length > 0 ? sum(previous12) : null,
        previous_12_month_average_actual_cents:
          previous12.length > 0 ? average(previous12, previous12.length) : null,
        latest_12_median_actual_cents: median(latest12),
        latest_12_standard_deviation_cents: populationStandardDeviation(latest12),
        latest_12_active_month_average_actual_cents:
          activeLatest12.length > 0 ? average(activeLatest12, activeLatest12.length) : null,
        latest_12_active_months: activeLatest12.length,
        latest_12_vs_previous_12_basis_points:
          previous12.length > 0 ? basisPoints(sum(latest12), sum(previous12)) : null,
        latest_6_vs_first_6_basis_points: basisPoints(latest6, first6),
        annualized_trend_basis_points: annualizedTrendBasisPoints(points, fullAverage),
        variability_basis_points: populationVariabilityBasisPoints(actuals, fullAverage),
        months_with_positive_budget: budgetPoints.length,
        months_over_positive_budget:
          budgetPoints.filter(point => point.actual > point.budgeted).length,
        largest_month_actual_cents: largest?.actual ?? null,
        largest_month: largest?.month ?? null,
      },
    };
  });
  rows.sort(
    (left, right) =>
      left.group.localeCompare(right.group) || left.category.localeCompare(right.category),
  );
  const matchedExceptionalNames = new Set(
    rows.filter(row => row.is_exceptional).map(row => row.category),
  );
  const unmatchedExceptionalNames = [...exceptionalNames]
    .filter(name => !matchedExceptionalNames.has(name));
  if (unmatchedExceptionalNames.length > 0) {
    throw new Error('one or more configured exceptional categories were not found');
  }

  const expenseRows = rows.filter(row => row.type === 'expense');
  const totalByMonth = ordered.map((_, index) =>
    sum(expenseRows.map(row => row.points[index].actual)));
  const underlyingByMonth = ordered.map((_, index) =>
    sum(expenseRows.filter(row => !row.is_exceptional).map(row => row.points[index].actual)));
  const exceptionalByMonth = ordered.map((_, index) =>
    sum(expenseRows.filter(row => row.is_exceptional).map(row => row.points[index].actual)));
  const latestTotal = totalByMonth.slice(-12);
  const previousTotal = totalByMonth.length > 12 ? totalByMonth.slice(-24, -12) : [];
  const latestUnderlying = underlyingByMonth.slice(-12);
  const previousUnderlying = underlyingByMonth.length > 12
    ? underlyingByMonth.slice(-24, -12)
    : [];
  const latestExceptional = exceptionalByMonth.slice(-12);
  const hasPositiveExpenseBudget = rows.some(row =>
    row.type === 'expense' && row.metrics.months_with_positive_budget > 0);

  const payload = {
    schema_version: 2,
    analysis_type: 'long_term_category_trends',
    analysis_mode: hasPositiveExpenseBudget ? 'budget_and_spend' : 'spend_only',
    start_month: ordered[0].month,
    end_month: ordered.at(-1).month,
    currency: String(currency || '').toUpperCase(),
    months_in_period: ordered.length,
    spend_summary: {
      latest_12_total_actual_cents: sum(latestTotal),
      previous_12_total_actual_cents: previousTotal.length > 0 ? sum(previousTotal) : null,
      latest_12_underlying_actual_cents: sum(latestUnderlying),
      previous_12_underlying_actual_cents:
        previousUnderlying.length > 0 ? sum(previousUnderlying) : null,
      latest_12_average_monthly_underlying_cents:
        average(latestUnderlying, latestUnderlying.length),
      latest_12_median_monthly_underlying_cents: median(latestUnderlying),
      latest_12_standard_deviation_monthly_underlying_cents:
        populationStandardDeviation(latestUnderlying),
      latest_12_vs_previous_12_underlying_basis_points:
        previousUnderlying.length > 0
          ? basisPoints(sum(latestUnderlying), sum(previousUnderlying))
          : null,
      latest_12_exceptional_actual_cents: sum(latestExceptional),
    },
    categories: rows.map((row, index) => ({
      ref: `c${String(index + 1).padStart(3, '0')}`,
      group: row.group,
      category: row.category,
      type: row.type,
      months_observed: row.observedMonths,
      active_in_latest_month: row.active_in_latest_month,
      is_exceptional: row.is_exceptional,
      available_evidence: [
        ...availableTrendEvidence(row.metrics, row.observedMonths),
        ...(row.is_exceptional ? ['exceptional_status'] : []),
      ],
      metrics: row.metrics,
    })),
  };
  return assertTrendOnlyPayload(payload);
}
