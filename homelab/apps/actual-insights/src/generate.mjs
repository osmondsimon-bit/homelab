// Orchestrates one explicitly requested month from Actual extraction through validated model persistence.
import { createHash } from 'node:crypto';

import { buildCategoryPayload } from './snapshot.mjs';

export function createMemoGenerator({
  extract,
  request,
  store,
  model,
  currentMonth = () => new Date().toISOString().slice(0, 7),
}) {
  let running = false;
  return async function generateMemo(targetMonth) {
    if (running) {
      throw new Error('monthly memo generation is already in progress');
    }
    running = true;
    try {
      if (!/^\d{4}-\d{2}$/.test(targetMonth) || targetMonth >= currentMonth()) {
        throw new Error('monthly memo requires a completed month');
      }
      const { currency, budgetMonths } = await extract(targetMonth);
      const payload = buildCategoryPayload({ targetMonth, currency, budgetMonths });
      const snapshotHash = createHash('sha256')
        .update(JSON.stringify(payload))
        .digest('hex');
      const result = await request({ payload, model });
      const id = store.save({
        month: targetMonth,
        snapshotHash,
        payload,
        memo: result.memo,
        model: result.model,
        responseId: result.responseId,
        usage: result.usage,
      });
      return { id, month: targetMonth, ...result };
    } finally {
      running = false;
    }
  };
}
