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
  'actual_vs_prior_3_month_basis_points',
  'budget_variance_cents',
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
  const history = ordered.slice(Math.max(0, targetIndex - 12), targetIndex).map(flattenMonth);
  const rows = [];
  for (const [key, target] of targetCategories) {
    const priorActuals = history
      .map(month => month.get(key))
      .filter(Boolean)
      .map(category => category.actual);
    const prior3 = average(priorActuals, 3);
    const prior12 = average(priorActuals, 12);
    rows.push({
      ...target,
      months_of_history: priorActuals.length,
      previous_month_actual_cents: priorActuals.at(-1) ?? null,
      prior_3_month_average_actual_cents: prior3,
      prior_12_month_average_actual_cents: prior12,
      actual_vs_prior_3_month_basis_points: basisPoints(target.actual, prior3),
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
        actual_vs_prior_3_month_basis_points:
          row.actual_vs_prior_3_month_basis_points,
        budget_variance_cents: row.budget_variance_cents,
      },
    })),
  };
  return assertCategoryOnlyPayload(payload);
}
