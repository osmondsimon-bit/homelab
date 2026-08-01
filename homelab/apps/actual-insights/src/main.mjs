// Wires the manual HTTP service to Actual's category reader, OpenAI, and local SQLite.
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import * as actualApi from '@actual-app/api';
import OpenAI from 'openai';

import { extractCategoryMonths } from './actual-client.mjs';
import { loadConfig } from './config.mjs';
import { createMemoGenerator } from './generate.mjs';
import { requestMemo } from './model.mjs';
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
const request = ({ payload, model }) => requestMemo({ client: openai, payload, model });
const generateMemo = createMemoGenerator({
  extract,
  request,
  store,
  model: config.model,
  currentMonth: () => currentMonthInTimeZone(config.timeZone),
});
const server = createInsightsServer({
  operatorLogin: config.operatorLogin,
  generateMemo,
  listMemos: () => store.list(),
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
