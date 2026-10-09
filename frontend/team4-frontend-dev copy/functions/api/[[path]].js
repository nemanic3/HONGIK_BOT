// Only proxy API paths. Private files and Django admin never enter Pages assets.
export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  const headers = {
    'Cache-Control': 'private, no-store, max-age=0',
    'CDN-Cache-Control': 'no-store',
    'Cloudflare-CDN-Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    'Vary': 'Authorization',
  };
  const unavailable = () => Response.json({ error: '서비스 서버 연결을 준비 중입니다.' }, { status: 503, headers });
  // Preview builds must never access the production database, even with bindings.
  if (url.origin !== env.PUBLIC_APP_ORIGIN || !env.API_ORIGIN || !env.HONGIK_PROXY_SECRET) return unavailable();
  let origin;
  try { origin = new URL(env.API_ORIGIN); } catch { return unavailable(); }
  if (origin.protocol !== 'https:' || origin.origin === url.origin || origin.pathname !== '/' || origin.search || origin.hash || origin.username || origin.password) return unavailable();
  if (!['GET', 'HEAD', 'POST', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'].includes(request.method)) return new Response(null, { status: 405, headers });
  const length = request.headers.get('content-length');
  if (length && Number(length) > 6 * 1024 * 1024) return Response.json({ error: '업로드 용량을 초과했습니다.' }, { status: 413, headers });
  const target = new URL(origin.origin);
  target.pathname = url.pathname;
  target.search = url.search;
  const forwarded = new Headers();
  for (const name of ['authorization', 'content-type', 'accept']) {
    if (request.headers.has(name)) forwarded.set(name, request.headers.get(name));
  }
  forwarded.set('X-Hongik-Proxy-Secret', env.HONGIK_PROXY_SECRET);
  forwarded.set('X-Forwarded-Proto', 'https');
  // Do not forward cookies, spoofable proxy headers, or arbitrary client secrets.
  try {
    const response = await fetch(target, {
      method: request.method,
      headers: forwarded,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
      redirect: 'manual',
      signal: AbortSignal.timeout(30000),
      cf: { cacheTtl: 0, cacheEverything: false },
    });
    if (response.status >= 300 && response.status < 400) return unavailable();
    const resultHeaders = new Headers(headers);
    for (const name of ['content-type', 'www-authenticate', 'retry-after']) {
      if (response.headers.has(name)) resultHeaders.set(name, response.headers.get(name));
    }
    return new Response(response.body, { status: response.status, headers: resultHeaders });
  } catch { return unavailable(); }
}
