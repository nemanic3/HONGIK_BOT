import test from 'node:test';
import assert from 'node:assert/strict';
import { component, hookHarness, render } from './component-loader.mjs';

function storage() {
  const data = new Map([['accessToken', 'old'], ['authSessionGeneration', 'old-session']]);
  return { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key) };
}

test('signup offers only the selector-supported canonical computer-engineering major', () => {
  const Signup = component('components/Header/SignUpModal.tsx');
  const html = render(Signup, { onClose() {} });
  assert.match(html, /<option value="컴퓨터공학과">컴퓨터공학과<\/option>/);
  assert.doesNotMatch(html, /<option value="(?:컴퓨터데이터공학부|전자전기공학부)"/);
});

test('profile correction requires an explicit supported major for an ambiguous legacy department', () => {
  const Profile = component('components/Header/ProfileModal.tsx');
  const html = render(Profile, { profile: { id: 42, major: '컴퓨터데이터공학부', admission_year: 2024, accreditation_track: 'accredited' }, onSaved() {}, onClose() {} });
  assert.match(html, /학과\/전공/);
  assert.match(html, /<option value="" selected="">학과\/전공을 직접 선택해주세요<\/option>/);
  assert.match(html, /<option value="컴퓨터공학과">컴퓨터공학과<\/option>/);
  assert.doesNotMatch(html, /<option value="컴퓨터공학과" selected=""/);
});

test('pending report is an evaluated unmet result, not asynchronous analysis progress', () => {
  const report = { status: 'pending', criteria: [], courses: [], by_semester: {}, warnings: [], policy: null };
  const harness = hookHarness([null, report, false, '', 0, false]);
  const Page = component('app/mypage/page.tsx', { react: harness.hooks, 'next/navigation': { useRouter: () => ({ push() {}, replace() {} }) } });
  const html = render(Page);
  assert.match(html, /충족하지 못한 졸업 요건/);
  assert.doesNotMatch(html, /분석 처리 중|잠시 후 새로고침/);
});

function findElement(tree, predicate) {
  if (Array.isArray(tree)) return tree.map(child => findElement(child, predicate)).find(Boolean);
  if (!tree || typeof tree !== 'object') return undefined;
  if (predicate(tree)) return tree;
  return findElement(tree.props?.children, predicate);
}

test('review row editor keeps a new row credit and semester unknown until explicit entry', () => {
  const doc = { schema_version: 1, source: { page: 2 }, courses: [] };
  const detail = { id: 42, status: 'complete', document: doc };
  const harness = hookHarness([detail, doc, JSON.stringify(doc), false, '', false, false, 0]);
  const Page = component('app/review/[id]/page.tsx', {
    react: harness.hooks,
    'next/navigation': { useParams: () => ({ id: '42' }), useRouter: () => ({ push() {} }) },
    '../../../components/Header/Header': { __esModule: true, default: () => null },
  });
  const tree = Page();
  findElement(tree, element => element.type === 'button' && element.props.children === '빈 과목 행 추가').props.onClick();
  const next = harness.updates.find(({ index }) => index === 1).next;
  assert.equal(next.courses[0].credit, null);
  assert.equal(next.courses[0].semester, null);
  assert.deepEqual(next.source, doc.source);
});

test('review loads nullable OCR rows and exposes editable blank inputs without discarding metadata', async () => {
  const doc = { schema_version: 1, source: { page: 2 }, courses: [{ code: '001009', name: 'Course', credit: null, type: '전필', grade: 'P', semester: null, confidence: 0.2 }] };
  const detail = { id: 42, status: 'complete', document: doc };
  const harness = hookHarness();
  const overrides = {
    react: harness.hooks,
    'next/navigation': { useParams: () => ({ id: '42' }), useRouter: () => ({ push() {} }) },
    '../../../components/Header/Header': { __esModule: true, default: () => null },
    '../../../lib/poll': { pollTranscript: async () => detail },
  };
  const Page = component('app/review/[id]/page.tsx', overrides);
  Page();
  const cleanup = harness.effects[1]();
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(harness.updates.filter(({ index }) => index === 1).at(-1).next, doc);
  cleanup();
  const loaded = hookHarness([detail, doc, JSON.stringify(doc), false, '', false, false, 0]);
  const tree = component('app/review/[id]/page.tsx', { ...overrides, react: loaded.hooks })();
  const credit = findElement(tree, element => element.props?.['aria-label'] === '1행 credit');
  assert.equal(credit.props.value, ''); assert.equal(credit.props.disabled, false);
  credit.props.onChange({ target: { value: '1.5' } });
  assert.deepEqual(loaded.updates.find(({ index }) => index === 1).next, { ...doc, courses: [{ ...doc.courses[0], credit: 1.5 }] });
  const semester = findElement(tree, element => element.props?.['aria-label'] === '1행 semester');
  assert.equal(semester.props.value, ''); assert.equal(semester.props.disabled, false);
});

test('dashboard lifecycle does not redirect after report 401 arrives behind completed same-session refresh and me retry', async () => {
  const { createApiClient, ApiError, errorMessage, SESSION_GENERATION_KEY } = await import('../lib/api.ts');
  const { getReport } = await import('../lib/flows.ts');
  const harness = hookHarness(); const listeners = new Map(); const redirects = []; const calls = [];
  const store = storage(); store.setItem('refreshToken', 'old-r');
  const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
  let releaseReport;
  const reportReply = new Promise(resolve => { releaseReport = resolve; });
  const profile = { id: 42, full_name: 'Same account' };
  const report = { status: 'pending', transcript_id: 42, criteria: [], courses: [], by_semester: {}, warnings: [], policy: null };
  const client = createApiClient({ baseUrl: 'http://api', storage: store, refreshPath: '/refresh/', fetcher: async (url, init) => {
    const token = init.headers.get('Authorization'); calls.push([url, token]);
    if (url.endsWith('/refresh/')) return json({ access: 'new', refresh: 'new-r' });
    if (url.includes('/report/') && token === 'Bearer old') return reportReply;
    if (token === 'Bearer old') return json({ detail: 'expired' }, 401);
    return json(url.endsWith('/me/') ? profile : report);
  } });
  const oldWindow = globalThis.window; const oldStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  globalThis.window = { location: { search: '?transcript_id=42' }, addEventListener: (name, callback) => listeners.set(name, callback), removeEventListener: name => listeners.delete(name) };
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: store });
  const Page = component('app/mypage/page.tsx', {
    react: harness.hooks,
    'next/navigation': { useRouter: () => ({ replace: path => redirects.push(path), push() {} }) },
    '../../lib/api': { api: () => client, ApiError, errorMessage, SESSION_GENERATION_KEY },
    '../../lib/flows': { getReport },
  });
  let disposeEvents; let disposeLoad;
  try {
    render(Page); disposeEvents = harness.effects[0](); disposeLoad = harness.effects[1]();
    await new Promise(resolve => setImmediate(resolve));
    assert.ok(harness.updates.some(({ index, next }) => index === 0 && next?.id === profile.id), '/me/ retry must complete before releasing report 401');
    assert.equal(store.getItem('accessToken'), 'new');
    releaseReport(json({ detail: 'expired' }, 401));
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(redirects, [], 'normal refresh must not redirect to /');
    assert.deepEqual(harness.updates.filter(({ index }) => index === 1).at(-1).next, report, 'actual dashboard accepts the recovered report');
    assert.ok(harness.updates.some(({ index, next }) => index === 2 && next === false), 'dashboard finishes loading');
    assert.deepEqual(calls.filter(([url]) => url.includes('/report/')).map(([, token]) => token), ['Bearer old', 'Bearer new']);
    assert.equal(calls.filter(([url]) => url.endsWith('/refresh/')).length, 1);
    assert.equal(store.getItem(SESSION_GENERATION_KEY), 'old-session');
    assert.equal(store.getItem('userId'), '42');
  } finally {
    releaseReport(json({}, 401)); disposeEvents?.(); disposeLoad?.(); globalThis.window = oldWindow;
    if (oldStorage) Object.defineProperty(globalThis, 'localStorage', oldStorage);
    else delete globalThis.localStorage;
  }
});

test('dashboard storage account switch aborts old reads, clears old state and reloads nonempty session', () => {
  const harness = hookHarness(); const listeners = new Map(); const redirects = []; const signals = [];
  const store = storage();
  const oldWindow = globalThis.window; const oldStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  globalThis.window = { location: { search: '?transcript_id=42' }, addEventListener: (name, callback) => listeners.set(name, callback), removeEventListener: name => listeners.delete(name) };
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: store });
  const client = { me: signal => { signals.push(signal); return new Promise(() => {}); } };
  const Page = component('app/mypage/page.tsx', {
    react: harness.hooks,
    'next/navigation': { useRouter: () => ({ replace: path => redirects.push(path), push() {} }) },
    '../../lib/api': { api: () => client, ApiError: class extends Error {}, errorMessage: String, SESSION_GENERATION_KEY: 'authSessionGeneration' },
    '../../lib/flows': { getReport: (_, id, signal) => { signals.push(signal); return new Promise(() => {}); } },
  });
  let disposeEvents; let disposeLoad;
  try {
    render(Page);
    disposeEvents = harness.effects[0](); disposeLoad = harness.effects[1]();
    store.setItem('authSessionGeneration', 'new-session'); store.setItem('accessToken', 'new');
    harness.updates.length = 0;
    listeners.get('storage')({ type: 'storage', key: 'accessToken', storageArea: store });
    assert.equal(signals[0].aborted, true, 'old account request must abort immediately');
    assert.ok(harness.updates.some(({ index, next }) => index === 0 && next === null), 'profile cleared');
    assert.ok(harness.updates.some(({ index, next }) => index === 1 && next === null), 'report cleared');
    assert.ok(harness.updates.some(({ index, next }) => index === 4 && typeof next === 'function' && next(0) === 1), 'reload new session');
    assert.deepEqual(redirects, []);
    harness.effects[1]();
    assert.equal(signals.at(-1).aborted, false, 'replacement reads use a fresh controller');
  } finally {
    disposeEvents?.(); disposeLoad?.(); globalThis.window = oldWindow;
    if (oldStorage) Object.defineProperty(globalThis, 'localStorage', oldStorage);
    else delete globalThis.localStorage;
  }
});
