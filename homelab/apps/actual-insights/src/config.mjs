// Loads non-secret settings from environment and all credentials from Docker secret files.
import { readFileSync } from 'node:fs';

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`missing required setting: ${name}`);
  return value;
}

function secret(pathName) {
  const value = readFileSync(required(pathName), 'utf8').trim();
  if (!value) throw new Error(`secret file is empty: ${pathName}`);
  return value;
}

function integer(name, fallback, minimum, maximum) {
  const value = Number.parseInt(process.env[name] || String(fallback), 10);
  if (!Number.isInteger(value) || value < minimum || value > maximum) {
    throw new Error(`${name} must be between ${minimum} and ${maximum}`);
  }
  return value;
}

export function loadConfig() {
  const operatorLogin = required('ACTUAL_INSIGHTS_OPERATOR_LOGIN');
  if (!operatorLogin.includes('@')) {
    throw new Error('ACTUAL_INSIGHTS_OPERATOR_LOGIN must be an email-style Tailscale login');
  }
  const currency = process.env.ACTUAL_INSIGHTS_CURRENCY || 'AUD';
  if (!/^[A-Z]{3}$/.test(currency)) {
    throw new Error('ACTUAL_INSIGHTS_CURRENCY must be a three-letter uppercase code');
  }
  const model = process.env.ACTUAL_INSIGHTS_MODEL || 'gpt-5.6-terra';
  if (!/^[A-Za-z0-9._-]+$/.test(model)) {
    throw new Error('ACTUAL_INSIGHTS_MODEL contains unsupported characters');
  }
  const timeZone = process.env.ACTUAL_INSIGHTS_TIME_ZONE || 'Etc/UTC';
  try {
    new Intl.DateTimeFormat('en', { timeZone }).format();
  } catch {
    throw new Error('ACTUAL_INSIGHTS_TIME_ZONE must be a valid IANA time zone');
  }
  return {
    operatorLogin,
    serverUrl: process.env.ACTUAL_SERVER_URL || 'http://actual:5006',
    serverPassword: secret('ACTUAL_SERVER_PASSWORD_FILE'),
    syncId: secret('ACTUAL_SYNC_ID_FILE'),
    encryptionPassword: secret('ACTUAL_E2EE_PASSWORD_FILE'),
    openaiApiKey: secret('OPENAI_API_KEY_FILE'),
    model,
    currency,
    timeZone,
    historyMonths: integer('ACTUAL_INSIGHTS_HISTORY_MONTHS', 24, 12, 24),
    port: integer('ACTUAL_INSIGHTS_PORT', 5007, 1024, 65535),
    databasePath: process.env.ACTUAL_INSIGHTS_DATABASE || '/data/insights.sqlite',
  };
}
