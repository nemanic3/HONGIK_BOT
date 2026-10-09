import test from 'node:test';
import assert from 'node:assert/strict';

function storage() {
  const data = new Map();
  return { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key) };
}
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };

test('two clients sharing storage reject an old me response after another account logs in', async () => {
  const { createApiClient } = await import('../lib/api.ts');
  const store = storage(); store.setItem('accessToken', 'old');
  const reply = deferred();
  const oldClient = createApiClient({ baseUrl: 'http://api', storage: store, fetcher: () => reply.promise });
  const newClient = createApiClient({ baseUrl: 'http://api', storage: store, fetcher: async url => url.endsWith('/login/') ? json({ access: 'new', refresh: 'new-r' }) : json({ id: 99 }) });
  const oldProfile = oldClient.me();
  newClient.logout();
  await newClient.login('new-account', 'test-password');
  reply.resolve(json({ id: 42 }));
  await assert.rejects(oldProfile, /세션/);
  assert.equal(store.getItem('userId'), '99');
  assert.equal(JSON.parse(store.getItem('user')).id, 99);
  assert.equal(store.getItem('accessToken'), 'new');
});

test('logout in another client invalidates a pending login even with no existing tokens', async () => {
  const { createApiClient } = await import('../lib/api.ts');
  const store = storage(); const reply = deferred(); let profileCalls = 0;
  const client = createApiClient({ baseUrl: 'http://api', storage: store, fetcher: url => {
    if (url.endsWith('/login/')) return reply.promise;
    profileCalls++; return Promise.resolve(json({ id: 42 }));
  } });
  const other = createApiClient({ baseUrl: 'http://api', storage: store });
  const login = client.login('old-account', 'test-password');
  other.logout(); reply.resolve(json({ access: 'old', refresh: 'old-r' }));
  await assert.rejects(login, /세션/);
  assert.equal(profileCalls, 0);
  assert.equal(store.getItem('accessToken'), null);
  assert.equal(store.getItem('user'), null);
});

for (const staleStatus of [200, 401]) {
  test(`overlapping logins keep the newer account when an older login returns ${staleStatus}`, async () => {
    const { createApiClient } = await import('../lib/api.ts');
    const store = storage(); const oldReply = deferred();
    const client = createApiClient({ baseUrl: 'http://api', storage: store, fetcher: async (url, init) => {
      if (url.endsWith('/login/')) return JSON.parse(init.body).student_id === 'old' ? oldReply.promise : json({ access: 'new', refresh: 'new-r' });
      return json({ id: 99 });
    } });
    const oldLogin = client.login('old', 'test-password');
    await client.login('new', 'test-password');
    oldReply.resolve(staleStatus === 200 ? json({ access: 'old', refresh: 'old-r' }) : json({ detail: 'Wrong password' }, 401));
    await assert.rejects(oldLogin);
    assert.equal(store.getItem('accessToken'), 'new');
    assert.equal(store.getItem('userId'), '99');
  });
}

test('an old login profile failure after cross-client logout/login must not logout the new account', async () => {
  const { createApiClient } = await import('../lib/api.ts');
  const store = storage(); const profileReply = deferred(); const profileStarted = deferred();
  const old = createApiClient({ baseUrl: 'http://api', storage: store, fetcher: async url => {
    if (url.endsWith('/login/')) return json({ access: 'old', refresh: 'old-r' });
    profileStarted.resolve(); return profileReply.promise;
  } });
  const fresh = createApiClient({ baseUrl: 'http://api', storage: store, fetcher: async url => url.endsWith('/login/') ? json({ access: 'new', refresh: 'new-r' }) : json({ id: 99 }) });
  const oldLogin = old.login('old', 'test-password'); await profileStarted.promise;
  fresh.logout(); await fresh.login('new', 'test-password');
  profileReply.resolve(json({ detail: 'expired' }, 401));
  await assert.rejects(oldLogin);
  assert.equal(store.getItem('accessToken'), 'new');
  assert.equal(store.getItem('userId'), '99');
});

test('new session refresh never joins a delayed refresh from the previous account', async () => {
  const { createApiClient } = await import('../lib/api.ts');
  const store = storage(); store.setItem('accessToken', 'old'); store.setItem('refreshToken', 'old-r');
  const oldRefresh = deferred(); const started = deferred(); let newRefreshes = 0;
  const client = createApiClient({ baseUrl: 'http://api', storage: store, refreshPath: '/refresh/', fetcher: async (url, init) => {
    if (url.endsWith('/login/')) return json({ access: 'new', refresh: 'new-r' });
    if (url.endsWith('/me/')) return json({ id: 99 });
    if (url.endsWith('/refresh/')) {
      if (JSON.parse(init.body).refresh === 'old-r') { started.resolve(); return oldRefresh.promise; }
      newRefreshes++; return json({ access: 'new-refreshed' });
    }
    return init.headers.get('Authorization') === 'Bearer new-refreshed' ? json({ ok: true }) : json({}, 401);
  } });
  const oldJob = client.request('/old/'); await started.promise;
  client.logout(); await client.login('new', 'test-password');
  const newJob = client.request('/new/');
  oldRefresh.resolve(json({ access: 'old-refreshed' }));
  const results = await Promise.allSettled([oldJob, newJob]);
  assert.equal(results[0].status, 'rejected');
  assert.equal(results[1].status, 'fulfilled');
  assert.equal(newRefreshes, 1);
  assert.equal(store.getItem('accessToken'), 'new-refreshed');
  assert.equal(store.getItem('userId'), '99');
});

test('default refresh route matches the backend users router', async () => {
  const { AUTH_REFRESH_PATH } = await import('../lib/api.ts');
  assert.equal(AUTH_REFRESH_PATH, '/api/users/refresh/');
});

test('signup error_message is preserved for the user', async () => {
  const { createApiClient } = await import('../lib/api.ts');
  const client = createApiClient({ baseUrl: 'http://api', storage: storage(), fetcher: async () => json({ error_message: '이미 등록된 학번입니다.' }, 400) });
  await assert.rejects(client.request('/api/users/signup/', {}, false), /이미 등록된 학번/);
});

test('logout during an ordinary profile request cannot repopulate stale identity', async () => {
  const { createApiClient } = await import('../lib/api.ts');
  const store = storage(); store.setItem('accessToken', 'a');
  let release;
  const client = createApiClient({ baseUrl: 'http://api', storage: store, fetcher: () => new Promise(resolve => { release = () => resolve(json({ id: 42 })); }) });
  const job = client.me();
  client.logout(); release();
  await assert.rejects(job, /세션/);
  assert.equal(store.getItem('user'), null);
});

test('HTTP errors stay readable without leaking HTML; request deadlines abort', async () => {
  const { createApiClient, errorMessage } = await import('../lib/api.ts');
  const store = storage(); store.setItem('accessToken', 'a');
  const invalid = createApiClient({ baseUrl: 'http://api', storage: store, fetcher: async () => json({ admission_year: ['This field is required.'] }, 400) });
  await assert.rejects(invalid.request('/a/'), error => error.message.includes('admission_year'));
  assert.equal(errorMessage(new Error('<html>secret debug page</html>')), '서버와 통신 중 문제가 발생했습니다.');
  let signal;
  const stalled = createApiClient({ baseUrl: 'http://api', storage: store, timeoutMs: 15, fetcher: (_, init) => { signal = init.signal; return new Promise(() => {}); } });
  await assert.rejects(stalled.request('/a/'), /시간/);
  assert.equal(signal.aborted, true);
});

test('logout during refresh cannot restore credentials or the previous account', async () => {
  const { createApiClient } = await import('../lib/api.ts');
  const store = storage(); store.setItem('accessToken', 'a'); store.setItem('refreshToken', 'r'); store.setItem('transcriptId', '42');
  let release;
  const client = createApiClient({ baseUrl: 'http://api', storage: store, refreshPath: '/refresh/', fetcher: url => url.endsWith('/refresh/') ? new Promise(resolve => { release = () => resolve(json({ access: 'new' })); }) : Promise.resolve(json({}, 401)) });
  const job = client.request('/a/');
  while (!release) await new Promise(resolve => setTimeout(resolve, 1));
  client.logout(); release();
  await assert.rejects(job);
  assert.equal(store.getItem('accessToken'), null);
  assert.equal(store.getItem('transcriptId'), null);
});

test('concurrent 401 responses share one configured refresh and retry once', async () => {
  const { createApiClient } = await import('../lib/api.ts');
  const store = storage(); store.setItem('accessToken', 'old'); store.setItem('refreshToken', 'r');
  let refreshes = 0;
  const client = createApiClient({ baseUrl: 'http://api', storage: store, refreshPath: '/refresh/', fetcher: async (url, init) => {
    if (url.endsWith('/refresh/')) { refreshes++; await new Promise(r => setTimeout(r, 5)); return json({ access: 'new' }); }
    return init.headers.get('Authorization') === 'Bearer new' ? json({ ok: true }) : json({ detail: 'expired' }, 401);
  } });
  assert.deepEqual(await Promise.all([client.request('/a/'), client.request('/b/')]), [{ ok: true }, { ok: true }]);
  assert.equal(refreshes, 1);
  assert.equal(store.getItem('accessToken'), 'new');
});

test('delayed report 401 after another request refreshes and retries uses the rotated same-session token once', async () => {
  const { createApiClient, SESSION_GENERATION_KEY } = await import('../lib/api.ts');
  const store = storage();
  store.setItem('accessToken', 'old'); store.setItem('refreshToken', 'old-r'); store.setItem(SESSION_GENERATION_KEY, 'same-session');
  const reportReply = deferred(); const calls = []; let refreshes = 0;
  const report = { status: 'pending', transcript_id: 42 };
  const client = createApiClient({ baseUrl: 'http://api', storage: store, refreshPath: '/refresh/', fetcher: async (url, init) => {
    const token = init.headers.get('Authorization'); calls.push([url, token]);
    if (url.endsWith('/refresh/')) { refreshes++; return json({ access: 'new', refresh: 'new-r' }); }
    if (url.endsWith('/report/') && token === 'Bearer old') return reportReply.promise;
    if (token === 'Bearer old') return json({ detail: 'expired' }, 401);
    return json(url.endsWith('/me/') ? { id: 42 } : report);
  } });
  const reportJob = client.request('/report/');
  assert.equal((await client.me()).id, 42); // Refresh and /me/ retry finish before the old report replies.
  reportReply.resolve(json({ detail: 'expired' }, 401));
  assert.deepEqual(await reportJob, report);
  assert.equal(refreshes, 1);
  assert.deepEqual(calls.filter(([url]) => url.endsWith('/report/')).map(([, token]) => token), ['Bearer old', 'Bearer new']);
  assert.equal(store.getItem('refreshToken'), 'new-r');
  assert.equal(store.getItem(SESSION_GENERATION_KEY), 'same-session');
  assert.equal(store.getItem('userId'), '42');
});

test('same-session original me 200 after another client rotates tokens remains valid and caches the profile', async () => {
  const { createApiClient, SESSION_GENERATION_KEY } = await import('../lib/api.ts');
  const store = storage(); store.setItem('accessToken', 'old'); store.setItem('refreshToken', 'old-r'); store.setItem(SESSION_GENERATION_KEY, 'same-session');
  const profileReply = deferred(); let profileCalls = 0;
  const reader = createApiClient({ baseUrl: 'http://api', storage: store, fetcher: () => { profileCalls++; return profileReply.promise; } });
  const refresher = createApiClient({ baseUrl: 'http://api', storage: store, refreshPath: '/refresh/', fetcher: async (url, init) => {
    if (url.endsWith('/refresh/')) return json({ access: 'new', refresh: 'new-r' });
    return init.headers.get('Authorization') === 'Bearer new' ? json({ ok: true }) : json({ detail: 'expired' }, 401);
  } });
  const profileJob = reader.me();
  await refresher.request('/report/');
  profileReply.resolve(json({ id: 42, full_name: 'Same account' }));
  assert.deepEqual(await profileJob, { id: 42, full_name: 'Same account' });
  assert.equal(profileCalls, 1, 'same-account 200 is accepted without another request');
  assert.equal(store.getItem('accessToken'), 'new'); assert.equal(store.getItem('refreshToken'), 'new-r');
  assert.equal(store.getItem(SESSION_GENERATION_KEY), 'same-session');
  assert.equal(store.getItem('userId'), '42');
  assert.deepEqual(JSON.parse(store.getItem('user')), { id: 42, full_name: 'Same account' });
});

test('delayed report 401 retries the current token only once and a genuine retry 401 logs out', async () => {
  const { createApiClient, ApiError, SESSION_GENERATION_KEY } = await import('../lib/api.ts');
  const store = storage(); store.setItem('accessToken', 'old'); store.setItem('refreshToken', 'old-r'); store.setItem(SESSION_GENERATION_KEY, 'same-session');
  const reportReply = deferred(); const reportTokens = []; let refreshes = 0; let logouts = 0;
  const client = createApiClient({ baseUrl: 'http://api', storage: store, refreshPath: '/refresh/', onLogout: () => { logouts++; }, fetcher: async (url, init) => {
    const token = init.headers.get('Authorization');
    if (url.endsWith('/refresh/')) { refreshes++; return json({ access: 'new', refresh: 'new-r' }); }
    if (url.endsWith('/report/')) { reportTokens.push(token); return token === 'Bearer old' ? reportReply.promise : json({ detail: 'revoked' }, 401); }
    return token === 'Bearer old' ? json({ detail: 'expired' }, 401) : json({ id: 42 });
  } });
  const reportJob = client.request('/report/');
  await client.me();
  reportReply.resolve(json({ detail: 'expired' }, 401));
  await assert.rejects(reportJob, error => error instanceof ApiError && error.status === 401 && error.message === 'revoked');
  assert.deepEqual(reportTokens, ['Bearer old', 'Bearer new']); assert.equal(refreshes, 1); assert.equal(logouts, 1);
  assert.notEqual(store.getItem(SESSION_GENERATION_KEY), 'same-session');
  for (const key of ['accessToken', 'refreshToken', 'user', 'userId']) assert.equal(store.getItem(key), null);
});

test('login fails closed when profile or tokens are invalid; identity only comes from /me/', async () => {
  const { createApiClient } = await import('../lib/api.ts');
  const store = storage();
  store.setItem('userId', '1');
  const calls = [];
  const client = createApiClient({ baseUrl: 'http://api', storage: store, fetcher: async (url, init) => { calls.push([url, init]); return url.endsWith('/login/') ? json({ access: 'access', refresh: 'refresh' }) : json({ detail: 'Unauthorized' }, 401); } });
  await assert.rejects(client.login('C123456', 'secret'));
  assert.equal(store.getItem('accessToken'), null);
  assert.equal(store.getItem('userId'), null);
  assert.equal(calls[1][0], 'http://api/api/users/me/');
  const valid = createApiClient({ baseUrl: 'http://api', storage: store, fetcher: async url => url.endsWith('/login/') ? json({ access: 'a', refresh: 'r' }) : json({ id: 42, full_name: 'Test', student_id: 'C123456' }) });
  assert.equal((await valid.login('C123456', 'secret')).id, 42);
  assert.equal(store.getItem('userId'), '42');
});


test('slow OCR uploads override the ordinary deadline and still honor cancellation', async () => {
  const { createApiClient } = await import('../lib/api.ts');
  const store = storage(); store.setItem('accessToken', 'test');
  let sent;
  const client = createApiClient({ baseUrl: 'http://api', storage: store, timeoutMs: 5, fetcher: async (_, init) => {
    sent = init;
    await new Promise(resolve => setTimeout(resolve, 25));
    return json({ transcript_id: 7 });
  } });
  assert.deepEqual(await client.request('/upload/', { timeoutMs: 200 }), { transcript_id: 7 });
  assert.equal('timeoutMs' in sent, false);
  const controller = new AbortController();
  const pending = client.request('/upload/', { timeoutMs: 200, signal: controller.signal });
  controller.abort(new Error('cancelled by user'));
  await assert.rejects(pending, /cancelled by user/);
});
