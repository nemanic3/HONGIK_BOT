import test from 'node:test';
import assert from 'node:assert/strict';
import { onRequest } from '../functions/api/[[path]].js';

const env = { PUBLIC_APP_ORIGIN: 'https://hongikbot.nemanic.dev', API_ORIGIN: 'https://hongikbot-origin.nemanic.dev', HONGIK_PROXY_SECRET: 'synthetic-proxy-test-only-not-a-real-secret' };

test('unconfigured and preview APIs fail closed without contacting production', async t => {
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async () => { calls++; throw new Error('must not run'); });
  for (const [url, configuration] of [
    ['https://preview.hongikbot.pages.dev/api/users/me/', env],
    ['https://hongikbot.nemanic.dev/api/users/me/', {}],
    ['https://hongikbot.nemanic.dev/api/users/me/', { ...env, API_ORIGIN: 'http://origin.example' }],
    ['https://hongikbot.nemanic.dev/api/users/me/', { ...env, API_ORIGIN: env.PUBLIC_APP_ORIGIN }],
  ]) {
    const response = await onRequest({ request: new Request(url), env: configuration });
    assert.equal(response.status, 503);
    assert.match(response.headers.get('Cache-Control'), /no-store/);
  }
  assert.equal(calls, 0);
});

test('proxy forwards bearer and multipart data while replacing client secrets and blocking caches', async t => {
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    assert.equal(String(url), 'https://hongikbot-origin.nemanic.dev/api/transcripts/42/?a=1');
    assert.equal(init.headers.get('Authorization'), 'Bearer synthetic');
    assert.equal(init.headers.get('X-Hongik-Proxy-Secret'), env.HONGIK_PROXY_SECRET);
    assert.equal(init.headers.get('X-Forwarded-Proto'), 'https');
    assert.equal(init.headers.get('Cookie'), null);
    assert.equal(await new Response(init.body).text(), 'synthetic upload');
    assert.equal(init.redirect, 'manual');
    assert.equal(init.cf.cacheTtl, 0);
    return Response.json({ transcript_id: 42 }, { status: 201, headers: { 'Cache-Control': 'public', 'Set-Cookie': 'private', 'Location': 'https://origin.example' } });
  });
  const request = new Request('https://hongikbot.nemanic.dev/api/transcripts/42/?a=1', {
    method: 'POST', body: 'synthetic upload', headers: { Authorization: 'Bearer synthetic', Cookie: 'private', 'X-Hongik-Proxy-Secret': 'spoofed', 'X-Forwarded-Proto': 'http' },
  });
  const response = await onRequest({ request, env });
  assert.equal(response.status, 201);
  assert.match(response.headers.get('Cache-Control'), /private, no-store/);
  assert.equal(response.headers.get('Set-Cookie'), null);
  assert.equal(response.headers.get('Location'), null);
  assert.equal(response.headers.get('X-Hongik-Proxy-Secret'), null);
  assert.deepEqual(await response.json(), { transcript_id: 42 });
});

test('redirect and upstream failure do not expose the origin, secrets, or internal errors', async t => {
  const request = new Request('https://hongikbot.nemanic.dev/api/users/me/');
  t.mock.method(globalThis, 'fetch', async () => new Response(null, { status: 302, headers: { Location: env.API_ORIGIN } }));
  let response = await onRequest({ request, env });
  assert.equal(response.status, 503);
  assert.equal(response.headers.get('Location'), null);
  globalThis.fetch = async () => { throw new Error(env.HONGIK_PROXY_SECRET); };
  response = await onRequest({ request, env });
  assert.equal(response.status, 503);
  assert.ok(!(await response.text()).includes(env.HONGIK_PROXY_SECRET));
});
