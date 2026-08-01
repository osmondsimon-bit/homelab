// Wires the manual HTTP service to Actual's category reader, OpenAI, and local SQLite.
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import * as actualApi from '@actual-app/api';
import OpenAI from 'openai';

import {
  extractCategoryMonths,
  extractCompletedCategoryHistory,
} from './actual-client.mjs';
import { loadConfig } from './config.mjs';
import {
  createMemoGenerator,
  createTrendGenerator,
} from './generate.mjs';
import {
  requestMemo,
  requestTrendMemo,
} from './model.mjs';
import { currentMonthInTimeZone } from './months.mjs';
import { createInsightsServer } from './server.mjs';
import { MemoStore } from './store.mjs';

const config = loadConfig();
const store = new MemoStore(config.databasePath);
const openai = new OpenAI({
  apiKey: config.openaiApiKey,
  maxRetries: 2,
  timeout: 120000,
});

const extract = targetMonth =>
  extractCategoryMonths({
    api: actualApi,
    targetMonth,
    historyMonths: config.historyMonths,
    currency: config.currency,
    cacheRoot: mkdtempSync(join(tmpdir(), 'actual-insights-')),
    serverUrl: config.serverUrl,
    serverPassword: config.serverPassword,
    syncId: config.syncId,
    encryptionPassword: config.encryptionPassword,
  });
const extractTrend = () =>
  extractCompletedCategoryHistory({
    api: actualApi,
    completedBeforeMonth: currentMonthInTimeZone(config.timeZone),
    historyMonths: 24,
    currency: config.currency,
    cacheRoot: mkdtempSync(join(tmpdir(), 'actual-insights-')),
    serverUrl: config.serverUrl,
    serverPassword: config.serverPassword,
    syncId: config.syncId,
    encryptionPassword: config.encryptionPassword,
  });
const request = ({ payload, model }) => requestMemo({ client: openai, payload, model });
const requestTrend = ({ payload, model }) =>
  requestTrendMemo({ client: openai, payload, model });
const monthlyGenerator = createMemoGenerator({
  extract,
  request,
  store,
  model: config.model,
  currentMonth: () => currentMonthInTimeZone(config.timeZone),
});
const trendGenerator = createTrendGenerator({
  extract: extractTrend,
  request: requestTrend,
  store,
  model: config.model,
});
let generationRunning = false;
async function exclusiveGeneration(operation) {
  if (generationRunning) {
    throw new Error('another insight generation is already in progress');
  }
  generationRunning = true;
  try {
    return await operation();
  } finally {
    generationRunning = false;
  }
}
const server = createInsightsServer({
  operatorLogin: config.operatorLogin,
  generateMemo: month => exclusiveGeneration(() => monthlyGenerator(month)),
  generateTrendMemo: () => exclusiveGeneration(() => trendGenerator()),
  listMemos: () => store.list(),
  publicOrigin: config.publicOrigin,
  timeZone: config.timeZone,
});

server.listen(config.port, '0.0.0.0', () => {
  console.log(`Actual insights listening on port ${config.port}`);
});

function stop() {
  server.close(() => {
    store.close();
    process.exit(0);
  });
}
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
