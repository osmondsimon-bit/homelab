// Serves the manual monthly memo UI behind a loopback-only Tailscale Serve proxy.
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { renderPage } from './render.mjs';
import { previousCompletedMonth } from './months.mjs';

const identityHeader = 'Tailscale-User-Login';

function normalizedPath(url) {
  const path = new URL(url, 'http://localhost').pathname;
  if (path === '/insights') return '/';
  if (path.startsWith('/insights/')) return path.slice('/insights'.length);
  return path;
}

function cookies(request) {
  return Object.fromEntries(
    String(request.headers.cookie || '')
      .split(';')
      .map(part => part.trim().split('='))
      .filter(parts => parts.length === 2),
  );
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
  listMemos,
  timeZone = 'Etc/UTC',
  logger = console,
}) {
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
      const csrf = randomBytes(24).toString('base64url');
      response.setHeader('Set-Cookie', `actual_insights_csrf=${csrf}; Path=/insights; Secure; HttpOnly; SameSite=Strict`);
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      response.end(renderPage({
        csrf,
        memos: await listMemos(),
        defaultMonth: previousCompletedMonth(timeZone),
      }));
      return;
    }

    if (path === '/generate' && request.method !== 'POST') {
      response.setHeader('Allow', 'POST');
      response.writeHead(405, { 'content-type': 'text/plain; charset=utf-8' });
      response.end('Method not allowed\n');
      return;
    }

    if (request.method === 'POST' && path === '/generate') {
      try {
        const protocol = request.headers['x-forwarded-proto'] || 'http';
        const expectedOrigin = `${protocol}://${request.headers.host}`;
        if (request.headers.origin !== expectedOrigin) {
          throw new Error('invalid request origin');
        }
        const form = await readForm(request);
        if (!equalTokens(cookies(request).actual_insights_csrf, form.get('csrf'))) {
          throw new Error('invalid CSRF token');
        }
        const month = form.get('month');
        if (!/^\d{4}-\d{2}$/.test(month || '')) {
          throw new Error('month must use YYYY-MM');
        }
        await generateMemo(month);
        response.writeHead(303, { location: '/insights/' });
        response.end();
      } catch (error) {
        const badRequest = /origin|CSRF|month|body/.test(error.message);
        if (!badRequest) logger.error('monthly memo generation failed');
        response.writeHead(badRequest ? 400 : 502, {
          'content-type': 'text/plain; charset=utf-8',
        });
        response.end(badRequest ? 'Invalid request\n' : 'Memo generation failed\n');
      }
      return;
    }

    response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
    response.end('Not found\n');
  });
}
