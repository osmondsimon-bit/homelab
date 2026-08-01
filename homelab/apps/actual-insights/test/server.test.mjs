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
  const page = await pageResponse.text();
  const csrf = page.match(/name="csrf" value="([^"]+)"/)?.[1];
  assert.equal(pageResponse.headers.get('set-cookie'), null);
  assert.ok(csrf);

  const postResponse = await fetch(`http://127.0.0.1:${port}/insights/generate`, {
    method: 'POST',
    headers: {
      ...headers,
      'content-type': 'application/x-www-form-urlencoded',
      host: `127.0.0.1:${port}`,
      origin: 'https://proxy-origin-is-not-a-backend-trust-input.example',
    },
    body: new URLSearchParams({ month: '2026-06', csrf }),
    redirect: 'manual',
  });
  assert.equal(postResponse.status, 303);
  assert.equal(calls, 1);

  const trendPageResponse = await fetch(`http://127.0.0.1:${port}/insights/`, {
    headers,
  });
  const trendCsrf = (await trendPageResponse.text()).match(
    /name="csrf" value="([^"]+)"/,
  )?.[1];

  const trendResponse = await fetch(`http://127.0.0.1:${port}/insights/generate-trends`, {
    method: 'POST',
    headers: {
      ...headers,
      'content-type': 'application/x-www-form-urlencoded',
      host: `127.0.0.1:${port}`,
      origin: 'https://another-proxy-origin.example',
    },
    body: new URLSearchParams({ csrf: trendCsrf }),
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

test('uses a one-time server-side token independent of rewritten proxy headers', async t => {
  let calls = 0;
  const server = await startServer({
    generateTrendMemo: async () => {
      calls += 1;
      return { id: 2 };
    },
  });
  t.after(() => server.close());
  const { port } = server.address();
  const identity = { 'tailscale-user-login': 'operator@example.com' };
  const pageResponse = await fetch(`http://127.0.0.1:${port}/insights/`, {
    headers: identity,
  });
  const csrf = (await pageResponse.text()).match(/name="csrf" value="([^"]+)"/)?.[1];
  assert.equal(pageResponse.headers.get('set-cookie'), null);

  const response = await fetch(`http://127.0.0.1:${port}/insights/generate-trends`, {
    method: 'POST',
    headers: {
      ...identity,
      'content-type': 'application/x-www-form-urlencoded',
      host: 'rewritten-backend.internal:5007',
      origin: 'https://actual.example.ts.net:8443',
    },
    body: new URLSearchParams({ csrf }),
    redirect: 'manual',
  });
  assert.equal(response.status, 303);
  assert.equal(calls, 1);

  const replayed = await fetch(`http://127.0.0.1:${port}/insights/generate-trends`, {
    method: 'POST',
    headers: {
      ...identity,
      'content-type': 'application/x-www-form-urlencoded',
      origin: 'https://actual.example.ts.net:8443',
    },
    body: new URLSearchParams({ csrf }),
  });
  assert.equal(replayed.status, 400);
  assert.equal(await replayed.text(), 'Invalid or expired CSRF token\n');
  assert.equal(calls, 1);
});

test('reports OpenAI quota exhaustion without leaking provider details', async t => {
  const providerError = Object.assign(new Error('sensitive provider response'), {
    code: 'insufficient_quota',
    status: 429,
  });
  const logged = [];
  const server = await startServer({
    generateTrendMemo: async () => {
      throw providerError;
    },
    logger: { error: message => logged.push(message) },
  });
  t.after(() => server.close());
  const { port } = server.address();
  const identity = { 'tailscale-user-login': 'operator@example.com' };
  const pageResponse = await fetch(`http://127.0.0.1:${port}/insights/`, {
    headers: identity,
  });
  const csrf = (await pageResponse.text()).match(/name="csrf" value="([^"]+)"/)?.[1];

  const response = await fetch(`http://127.0.0.1:${port}/insights/generate-trends`, {
    method: 'POST',
    headers: {
      ...identity,
      'content-type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({ csrf }),
  });

  assert.equal(response.status, 503);
  assert.equal(
    await response.text(),
    'OpenAI API quota unavailable. Check project billing and limits.\n',
  );
  assert.deepEqual(logged, ['insight generation failed: openai_insufficient_quota']);
  assert.equal(logged.join(' ').includes('sensitive provider response'), false);
});
