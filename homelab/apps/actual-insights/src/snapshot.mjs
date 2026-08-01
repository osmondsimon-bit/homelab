// Converts Actual's budget-month objects into the only data shape permitted to cross the LLM boundary.

const rootFields = new Set(['schema_version', 'target_month', 'currency', 'categories']);
const categoryFields = new Set([
  'ref',
  'group',
  'category',
  'type',
  'months_of_history',
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
  'start_month',
  'end_month',
  'currency',
  'months_in_period',
  'categories',
]);
const trendCategoryFields = new Set([
  'ref',
  'group',
  'category',
  'type',
  'months_observed',
  'active_in_latest_month',
  'metrics',
]);
const trendMetricFields = new Set([
  'total_actual_cents',
  'full_period_average_actual_cents',
  'first_6_month_average_actual_cents',
  'latest_6_month_average_actual_cents',
  'latest_12_month_average_actual_cents',
  'latest_6_vs_first_6_basis_points',
  'annualized_trend_basis_points',
  'variability_basis_points',
  'months_with_budget',
  'months_over_budget',
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

export function assertCategoryOnlyPayload(payload) {
  assertExactFields(payload, rootFields, 'payload');
  if (payload.schema_version !== 1) {
    throw new Error('unsupported category payload schema version');
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
  if (payload.schema_version !== 1 || payload.analysis_type !== 'long_term_category_trends') {
    throw new Error('unsupported long-term category payload contract');
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

  const refs = new Set();
  for (const [index, category] of payload.categories.entries()) {
    assertExactFields(category, trendCategoryFields, `trend categories[${index}]`);
    assertExactFields(category.metrics, trendMetricFields, `trend categories[${index}].metrics`);
    if (!/^c\d{3,}$/.test(category.ref) || refs.has(category.ref)) {
      throw new Error('trend category refs must be unique local references');
    }
    refs.add(category.ref);
    assertCategoryLabel(category);
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
    const priorActuals = history
      .map(month => month.get(key))
      .filter(Boolean)
      .map(category => category.actual);
    const prior3 = average(priorActuals, 3);
    const prior12 = average(priorActuals, 12);
    const prior24 = average(priorActuals, 24);
    rows.push({
      ...target,
      months_of_history: priorActuals.length,
      previous_month_actual_cents: priorActuals.at(-1) ?? null,
      prior_3_month_average_actual_cents: prior3,
      prior_12_month_average_actual_cents: prior12,
      prior_24_month_average_actual_cents: prior24,
      actual_vs_prior_3_month_basis_points: basisPoints(target.actual, prior3),
      actual_vs_prior_24_month_basis_points: basisPoints(target.actual, prior24),
      budget_variance_cents:
        target.budgeted === null ? null : target.budgeted - target.actual,
    });
  }
  rows.sort(
    (left, right) =>
      left.group.localeCompare(right.group) || left.category.localeCompare(right.category),
  );

  const payload = {
    schema_version: 1,
    target_month: targetMonth,
    currency: String(currency || '').toUpperCase(),
    categories: rows.map((row, index) => ({
      ref: `c${String(index + 1).padStart(3, '0')}`,
      group: row.group,
      category: row.category,
      type: row.type,
      months_of_history: row.months_of_history,
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

export function buildTrendPayload({ currency, budgetMonths }) {
  const ordered = [...budgetMonths]
    .filter(month => month && /^\d{4}-\d{2}$/.test(month.month))
    .sort((left, right) => left.month.localeCompare(right.month))
    .slice(-24);
  if (ordered.length === 0) {
    throw new Error('long-term analysis requires completed budget months');
  }

  const flattened = ordered.map(flattenMonth);
  const records = new Map();
  for (const [monthIndex, month] of flattened.entries()) {
    for (const [key, category] of month) {
      const record = records.get(key) || { points: [] };
      record.group = category.group;
      record.category = category.category;
      record.type = category.type;
      record.points.push({
        index: monthIndex,
        month: ordered[monthIndex].month,
        actual: category.actual,
        budgeted: category.budgeted,
      });
      records.set(key, record);
    }
  }

  const rows = [...records.entries()].map(([key, record]) => {
    const actuals = record.points.map(point => point.actual);
    const fullAverage = average(actuals, actuals.length);
    const first6 = average(actuals.slice(0, 6), 6);
    const latest6 = average(actuals, 6);
    const budgetPoints = record.points.filter(point => point.budgeted !== null);
    const largest = record.points.reduce(
      (selected, point) => (selected === null || point.actual > selected.actual ? point : selected),
      null,
    );
    return {
      key,
      ...record,
      active_in_latest_month: flattened.at(-1).has(key),
      metrics: {
        total_actual_cents: actuals.reduce((sum, value) => sum + value, 0),
        full_period_average_actual_cents: fullAverage,
        first_6_month_average_actual_cents: first6,
        latest_6_month_average_actual_cents: latest6,
        latest_12_month_average_actual_cents: average(actuals, 12),
        latest_6_vs_first_6_basis_points: basisPoints(latest6, first6),
        annualized_trend_basis_points: annualizedTrendBasisPoints(record.points, fullAverage),
        variability_basis_points: populationVariabilityBasisPoints(actuals, fullAverage),
        months_with_budget: budgetPoints.length,
        months_over_budget: budgetPoints.filter(point => point.actual > point.budgeted).length,
        largest_month_actual_cents: largest?.actual ?? null,
        largest_month: largest?.month ?? null,
      },
    };
  });
  rows.sort(
    (left, right) =>
      left.group.localeCompare(right.group) || left.category.localeCompare(right.category),
  );

  const payload = {
    schema_version: 1,
    analysis_type: 'long_term_category_trends',
    start_month: ordered[0].month,
    end_month: ordered.at(-1).month,
    currency: String(currency || '').toUpperCase(),
    months_in_period: ordered.length,
    categories: rows.map((row, index) => ({
      ref: `c${String(index + 1).padStart(3, '0')}`,
      group: row.group,
      category: row.category,
      type: row.type,
      months_observed: row.points.length,
      active_in_latest_month: row.active_in_latest_month,
      metrics: row.metrics,
    })),
  };
  return assertTrendOnlyPayload(payload);
}
