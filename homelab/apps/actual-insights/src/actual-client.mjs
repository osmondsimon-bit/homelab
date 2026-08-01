// Reads only Actual budget-month/category methods and destroys the decrypted client cache after each run.
import { rmSync } from 'node:fs';

async function withDownloadedBudget({
  api,
  cacheRoot,
  serverUrl,
  serverPassword,
  syncId,
  encryptionPassword,
  read,
}) {
  let initialized = false;
  try {
    await api.init({
      dataDir: cacheRoot,
      serverURL: serverUrl,
      password: serverPassword,
      verbose: false,
    });
    initialized = true;
    await api.downloadBudget(syncId, { password: encryptionPassword });
    return await read(api);
  } catch {
    throw new Error('Actual category extraction failed');
  } finally {
    if (initialized) {
      try {
        await api.shutdown();
      } catch {
        // Cache destruction is the required cleanup even if the client cannot shut down cleanly.
      }
    }
    rmSync(cacheRoot, { recursive: true, force: true });
  }
}

export async function extractCategoryMonths({
  api,
  targetMonth,
  historyMonths,
  currency,
  cacheRoot,
  serverUrl,
  serverPassword,
  syncId,
  encryptionPassword,
}) {
  return withDownloadedBudget({
    api,
    cacheRoot,
    serverUrl,
    serverPassword,
    syncId,
    encryptionPassword,
    read: async client => {
      const availableMonths = (await client.getBudgetMonths()).sort();
      const targetIndex = availableMonths.indexOf(targetMonth);
      if (targetIndex === -1) {
        throw new Error('target month is not available');
      }
      const selectedMonths = availableMonths.slice(
        Math.max(0, targetIndex - historyMonths),
        targetIndex + 1,
      );
      const budgetMonths = [];
      for (const month of selectedMonths) {
        budgetMonths.push(await client.getBudgetMonth(month));
      }
      return { currency, budgetMonths };
    },
  });
}

export async function extractCompletedCategoryHistory({
  api,
  completedBeforeMonth,
  historyMonths,
  currency,
  cacheRoot,
  serverUrl,
  serverPassword,
  syncId,
  encryptionPassword,
}) {
  return withDownloadedBudget({
    api,
    cacheRoot,
    serverUrl,
    serverPassword,
    syncId,
    encryptionPassword,
    read: async client => {
      const selectedMonths = (await client.getBudgetMonths())
        .filter(month => month < completedBeforeMonth)
        .sort()
        .slice(-historyMonths);
      const budgetMonths = [];
      for (const month of selectedMonths) {
        budgetMonths.push(await client.getBudgetMonth(month));
      }
      return { currency, budgetMonths };
    },
  });
}
