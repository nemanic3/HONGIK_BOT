import type { UserProfile } from './types';

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? (process.env.NODE_ENV === 'production' ? '' : 'http://127.0.0.1:8000')).replace(/\/$/, '');
export const AUTH_REFRESH_PATH = process.env.NEXT_PUBLIC_AUTH_REFRESH_PATH || '/api/users/refresh/';
const SESSION_KEYS = ['accessToken', 'refreshToken', 'userId', 'user_id', 'accessExp', 'fullName', 'fullname', 'full_name', 'studentId', 'StudentId', 'currentYear', 'major', 'user', 'transcriptId', 'token', 'authToken'];
export const SESSION_GENERATION_KEY = 'authSessionGeneration';

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
const GENERIC_ERROR = '서버와 통신 중 문제가 발생했습니다.';
function responseMessage(data: unknown, status: number): string {
  if (data && typeof data === 'object') {
    const fields = data as Record<string, unknown>;
    for (const key of ['detail', 'error', 'error_message', 'message']) if (typeof fields[key] === 'string' && !(fields[key] as string).includes('<')) return (fields[key] as string).slice(0, 500);
    const messages = Object.entries(fields).filter(([, value]) => Array.isArray(value) && value.every(item => typeof item === 'string')).map(([key, value]) => `${key}: ${(value as string[]).join(' ')}`);
    if (messages.length) return messages.join('\n').slice(0, 500);
  }
  return `요청 실패 (${status})`;
}
export function errorMessage(error: unknown): string {
  return error instanceof Error && error.message && !error.message.includes('<') ? error.message.slice(0, 500) : GENERIC_ERROR;
}
export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(message: string, status: number, data?: unknown) { super(message); this.name = 'ApiError'; this.status = status; this.data = data; }
}
export function createApiClient(options: { baseUrl: string; storage: Store; fetcher?: typeof fetch; refreshPath?: string; timeoutMs?: number; onLogout?: () => void }) {
  const store = options.storage;
  const fetcher = options.fetcher ?? fetch;
  let refreshing: { session: ReturnType<typeof identity>; promise: Promise<void> } | undefined;
  const identity = () => ({ generation: store.getItem(SESSION_GENERATION_KEY), access: store.getItem('accessToken'), refresh: store.getItem('refreshToken') });
  const isCurrent = (session: ReturnType<typeof identity>) => {
    const current = identity();
    return session.generation === current.generation && session.access === current.access && session.refresh === current.refresh;
  };
  function logout() {
    // Keep the tombstone even without tokens: logout also invalidates pending login attempts in other tabs.
    store.setItem(SESSION_GENERATION_KEY, crypto.randomUUID());
    SESSION_KEYS.forEach(key => store.removeItem(key)); options.onLogout?.();
  }
  async function signOut() {
    const access = store.getItem('accessToken');
    const refreshToken = store.getItem('refreshToken');
    logout();
    if (!access || !refreshToken) return;
    try {
      await fetcher(options.baseUrl + '/api/users/logout/', {
        method: 'POST', cache: 'no-store', signal: AbortSignal.timeout(15000),
        headers: { Authorization: `Bearer ${access}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: refreshToken }),
      });
    } catch { /* Local sign-out already completed even if the server is offline. */ }
  }
  async function refresh() {
    if (refreshing && isCurrent(refreshing.session)) return refreshing.promise;
    const session = identity();
    const refreshToken = session.refresh;
    if (!options.refreshPath || !/^\/(?!\/)/.test(options.refreshPath) || !refreshToken) { logout(); throw new ApiError('세션이 만료되었습니다. 다시 로그인해주세요. (갱신 경로 미설정 또는 토큰 없음)', 401); }
    const promise = (async () => {
      try {
        const tokens = await request<{ access: string; refresh?: string }>(options.refreshPath!, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh: refreshToken }) }, false);
        if (!isCurrent(session)) throw new ApiError('세션이 종료되었습니다.', 401);
        if (typeof tokens?.access !== 'string' || !tokens.access) throw new ApiError('토큰 갱신 응답이 올바르지 않습니다.', 401);
        store.setItem('accessToken', tokens.access);
        if (typeof tokens.refresh === 'string' && tokens.refresh) store.setItem('refreshToken', tokens.refresh);
      } catch (error) { if (isCurrent(session)) logout(); throw error; }
      finally { if (refreshing?.promise === promise) refreshing = undefined; }
    })();
    refreshing = { session, promise };
    return promise;
  }
  async function request<T>(path: string, init: RequestInit & { timeoutMs?: number } = {}, authenticated = true, retry = true, accept?: (data: T) => void): Promise<T> {
    const { timeoutMs, ...fetchInit } = init;
    const session = identity();
    const headers = new Headers(init.headers);
    if (authenticated) {
      const token = store.getItem('accessToken');
      if (!token) throw new ApiError('로그인이 필요합니다.', 401);
      headers.set('Authorization', `Bearer ${token}`);
    }
    const controller = new AbortController();
    const cancel = () => controller.abort(init.signal?.reason ?? new DOMException('Cancelled', 'AbortError'));
    init.signal?.addEventListener('abort', cancel, { once: true });
    if (init.signal?.aborted) cancel();
    const timer = setTimeout(() => controller.abort(new Error('서버 응답 시간이 초과되었습니다. 다시 시도해주세요.')), timeoutMs ?? options.timeoutMs ?? 30000);
    let rejectAbort: () => void;
    const aborted = new Promise<never>((_, reject) => {
      rejectAbort = () => reject(controller.signal.reason);
      controller.signal.addEventListener('abort', rejectAbort, { once: true });
      if (controller.signal.aborted) rejectAbort();
    });
    let response: Response;
    let data: unknown;
    try {
      response = await Promise.race([fetcher(options.baseUrl + path, { ...fetchInit, signal: controller.signal, headers, cache: 'no-store' }), aborted]);
      data = await Promise.race([response.json().catch(() => null), aborted]);
    } finally { clearTimeout(timer); init.signal?.removeEventListener('abort', cancel); controller.signal.removeEventListener('abort', rejectAbort!); }
    if (init.signal?.aborted) throw init.signal.reason;
    // Generation changes on logout/login, not on same-account token rotation.
    if (authenticated && (session.generation !== store.getItem(SESSION_GENERATION_KEY) || !store.getItem('accessToken'))) throw new ApiError('세션이 종료되었습니다.', 401);
    if (response.status === 401 && authenticated) {
      if (retry) {
        // A delayed 401 may belong to the token already replaced by this session's refresh.
        if (isCurrent(session)) await refresh();
        if (session.generation !== store.getItem(SESSION_GENERATION_KEY)) throw new ApiError('세션이 종료되었습니다.', 401);
        return request<T>(path, init, true, false, accept);
      }
      if (isCurrent(session)) logout();
    }
    if (!response.ok) throw new ApiError(responseMessage(data, response.status), response.status, data);
    accept?.(data as T);
    return data as T;
  }
  async function me(signal?: AbortSignal): Promise<UserProfile> {
    // Cache in the same synchronous acceptance step as the identity check, not after an await.
    return request<UserProfile>('/api/users/me/', { signal }, true, true, profile => {
      if (!profile || !Number.isSafeInteger(profile.id) || profile.id <= 0) throw new ApiError('사용자 ID를 확인할 수 없습니다.', 502);
      store.setItem('user', JSON.stringify(profile));
      store.setItem('userId', String(profile.id));
    });
  }
  async function login(student_id: string, password: string, signal?: AbortSignal) {
    logout();
    const attempt = store.getItem(SESSION_GENERATION_KEY);
    const isAttemptCurrent = () => attempt === store.getItem(SESSION_GENERATION_KEY);
    try {
      const tokens = await request<{ access: string; refresh: string }>('/api/users/login/', { method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ student_id, password }) }, false);
      if (!isAttemptCurrent()) throw new ApiError('세션이 종료되었습니다.', 401);
      if (!tokens || typeof tokens.access !== 'string' || !tokens.access || typeof tokens.refresh !== 'string' || !tokens.refresh) throw new ApiError('로그인 응답에 토큰이 없습니다.', 502);
      store.setItem('accessToken', tokens.access);
      store.setItem('refreshToken', tokens.refresh);
      const profile = await me(signal);
      if (!isAttemptCurrent()) throw new ApiError('세션이 종료되었습니다.', 401);
      return profile;
    } catch (error) { if (isAttemptCurrent()) logout(); throw error; }
  }
  return { request, login, logout, signOut, me };
}
let shared: ReturnType<typeof createApiClient> | undefined;
export function api() {
  if (typeof window === 'undefined') throw new Error('브라우저에서만 API를 사용할 수 있습니다.');
  return shared ??= createApiClient({ baseUrl: API_BASE_URL, storage: localStorage, refreshPath: AUTH_REFRESH_PATH, onLogout: () => window.dispatchEvent(new Event('user-updated')) });
}
