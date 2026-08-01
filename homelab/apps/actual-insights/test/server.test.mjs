// HTTP contract tests for manual-only generation behind Tailscale Serve.
import assert from 'node:assert/strict';
import test from 'node:test';

import { createInsightsServer } from '../src/server.mjs';

async function startServer(options = {}) {
  const server = createInsightsServer({
    operatorLogin: 'operator@example.com',
    generateMemo: async month => ({ month, id: 1 }),
    generateTrendMemo: async () => ({ id: 2 }),
    listMemos: () => [],
    ...options,
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return server;
}

test('requires the Tailscale operator identity', async t => {
  const server = await startServer();
  t.after(() => server.close());
  const { port } = server.address();

  const response = await fetch(`http://127.0.0.1:${port}/insights/`);
  assert.equal(response.status, 403);
});

test('generation exists only as an authenticated manual POST', async t => {
  let calls = 0;
  let trendCalls = 0;
  const server = await startServer({
    generateMemo: async month => {
      calls += 1;
      return { month, id: 1 };
    },
    generateTrendMemo: async () => {
      trendCalls += 1;
      return { id: 2 };
    },
  });
  t.after(() => server.close());
  const { port } = server.address();
  const headers = { 'tailscale-user-login': 'operator@example.com' };

  const getResponse = await fetch(`http://127.0.0.1:${port}/insights/generate`, {
    headers,
  });
  assert.equal(getResponse.status, 405);
  assert.equal(calls, 0);

  const pageResponse = await fetch(`http://127.0.0.1:${port}/insights/`, {
    headers,
  });
  assert.equal(pageResponse.status, 200);
  const cookie = pageResponse.headers.get('set-cookie');
  const page = await pageResponse.text();
  const csrf = page.match(/name="csrf" value="([^"]+)"/)?.[1];
  assert.ok(cookie);
  assert.ok(csrf);

  const postResponse = await fetch(`http://127.0.0.1:${port}/insights/generate`, {
    method: 'POST',
    headers: {
      ...headers,
      cookie: cookie.split(';')[0],
      'content-type': 'application/x-www-form-urlencoded',
      host: `127.0.0.1:${port}`,
      origin: `http://127.0.0.1:${port}`,
    },
    body: new URLSearchParams({ month: '2026-06', csrf }),
    redirect: 'manual',
  });
  assert.equal(postResponse.status, 303);
  assert.equal(calls, 1);

  const trendResponse = await fetch(`http://127.0.0.1:${port}/insights/generate-trends`, {
    method: 'POST',
    headers: {
      ...headers,
      cookie: cookie.split(';')[0],
      'content-type': 'application/x-www-form-urlencoded',
      host: `127.0.0.1:${port}`,
      origin: `http://127.0.0.1:${port}`,
    },
    body: new URLSearchParams({ csrf }),
    redirect: 'manual',
  });
  assert.equal(trendResponse.status, 303);
  assert.equal(trendCalls, 1);
});

test('health is available locally without exposing financial state', async t => {
  const server = await startServer();
  t.after(() => server.close());
  const { port } = server.address();
  const response = await fetch(`http://127.0.0.1:${port}/healthz`);

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: 'ok' });
});
