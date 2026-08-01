// Serves manual category insights behind a loopback-only, identity-aware Tailscale Serve proxy.
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { renderPage } from './render.mjs';
import { previousCompletedMonth } from './months.mjs';

const identityHeader = 'Tailscale-User-Login';
const safeClientErrors = new Map([
  ['invalid or expired CSRF token', 'Invalid or expired CSRF token\n'],
  ['month must use YYYY-MM', 'Invalid completed month\n'],
  ['request body is too large', 'Request body is too large\n'],
]);

function normalizedPath(url) {
  const path = new URL(url, 'http://localhost').pathname;
  if (path === '/insights') return '/';
  if (path.startsWith('/insights/')) return path.slice('/insights'.length);
  return path;
}

function equalTokens(left, right) {
  if (!left || !right) return false;
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  return leftBuffer.length === rightBuffer.length && timingSafeEqual(leftBuffer, rightBuffer);
}

function securityHeaders(response) {
  response.setHeader('Content-Security-Policy', "default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'self'");
  response.setHeader('Referrer-Policy', 'no-referrer');
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('X-Frame-Options', 'SAMEORIGIN');
  response.setHeader('Cache-Control', 'no-store');
}

async function readForm(request) {
  let body = '';
  for await (const chunk of request) {
    body += chunk;
    if (body.length > 8192) {
      throw new Error('request body is too large');
    }
  }
  return new URLSearchParams(body);
}

export function createInsightsServer({
  operatorLogin,
  generateMemo,
  generateTrendMemo,
  listMemos,
  timeZone = 'Etc/UTC',
  logger = console,
}) {
  const csrfTokens = new Map();
  const csrfLifetimeMs = 30 * 60 * 1000;
  function pruneCsrfTokens(now = Date.now()) {
    for (const [token, expiresAt] of csrfTokens) {
      if (expiresAt <= now) csrfTokens.delete(token);
    }
    while (csrfTokens.size > 32) {
      csrfTokens.delete(csrfTokens.keys().next().value);
    }
  }
  function issueCsrfToken() {
    const token = randomBytes(24).toString('base64url');
    csrfTokens.set(token, Date.now() + csrfLifetimeMs);
    pruneCsrfTokens();
    return token;
  }
  function consumeCsrfToken(candidate) {
    pruneCsrfTokens();
    for (const token of csrfTokens.keys()) {
      if (equalTokens(token, candidate)) {
        csrfTokens.delete(token);
        return true;
      }
    }
    return false;
  }
  const appRoot = dirname(dirname(fileURLToPath(import.meta.url)));
  const assets = {
    '/assets/pico.min.css': join(appRoot, 'node_modules/@picocss/pico/css/pico.min.css'),
    '/assets/app.css': join(appRoot, 'public/app.css'),
  };
  return createServer(async (request, response) => {
    securityHeaders(response);
    const path = normalizedPath(request.url);

    if (request.method === 'GET' && path === '/healthz') {
      response.writeHead(200, { 'content-type': 'application/json' });
      response.end(JSON.stringify({ status: 'ok' }));
      return;
    }

    const login = request.headers[identityHeader.toLowerCase()];
    if (login !== operatorLogin) {
      response.writeHead(403, { 'content-type': 'text/plain; charset=utf-8' });
      response.end('Forbidden\n');
      return;
    }

    if (request.method === 'GET' && assets[path]) {
      response.writeHead(200, { 'content-type': 'text/css; charset=utf-8' });
      response.end(readFileSync(assets[path]));
      return;
    }

    if (request.method === 'GET' && path === '/') {
      const csrf = issueCsrfToken();
      const requestedSort = new URL(request.url, 'http://localhost').searchParams.get('sort');
      const categorySort = ['category', 'latest12', 'average', 'change', 'deviation']
        .includes(requestedSort)
        ? requestedSort
        : 'latest12';
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      response.end(renderPage({
        csrf,
        memos: await listMemos(),
        defaultMonth: previousCompletedMonth(timeZone),
        categorySort,
      }));
      return;
    }

    const generationPath = path === '/generate' || path === '/generate-trends';
    if (generationPath && request.method !== 'POST') {
      response.setHeader('Allow', 'POST');
      response.writeHead(405, { 'content-type': 'text/plain; charset=utf-8' });
      response.end('Method not allowed\n');
      return;
    }

    if (request.method === 'POST' && generationPath) {
      try {
        const form = await readForm(request);
        if (!consumeCsrfToken(form.get('csrf'))) {
          throw new Error('invalid or expired CSRF token');
        }
        if (path === '/generate') {
          const month = form.get('month');
          if (!/^\d{4}-\d{2}$/.test(month || '')) {
            throw new Error('month must use YYYY-MM');
          }
          await generateMemo(month);
        } else {
          await generateTrendMemo();
        }
        response.writeHead(303, { location: '/insights/' });
        response.end();
      } catch (error) {
        const clientMessage = safeClientErrors.get(error.message);
        const badRequest = clientMessage !== undefined;
        const quotaUnavailable = error.code === 'insufficient_quota';
        const invalidModelOutput = error.code === 'model_output_invalid';
        if (quotaUnavailable) {
          logger.error('insight generation failed: openai_insufficient_quota');
        } else if (invalidModelOutput) {
          logger.error('insight generation failed: model_output_invalid');
        } else if (!badRequest) {
          logger.error('insight generation failed');
        }
        response.writeHead(badRequest ? 400 : quotaUnavailable ? 503 : 502, {
          'content-type': 'text/plain; charset=utf-8',
        });
        response.end(
          badRequest
            ? clientMessage
            : quotaUnavailable
              ? 'OpenAI API quota unavailable. Check project billing and limits.\n'
              : invalidModelOutput
                ? 'Model response did not pass memo safety checks after one retry.\n'
                : 'Memo generation failed\n',
        );
      }
      return;
    }

    response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
    response.end('Not found\n');
  });
}
