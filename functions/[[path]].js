export async function onRequest(context) {
  const url = new URL(context.request.url);
  const backendPaths = ['/api/', '/spaces', '/rollout', '/jobs', '/audit', '/healthz'];
  
  const isApi = backendPaths.some(p => url.pathname === p || url.pathname.startsWith(p + '/') || url.pathname.startsWith(p + '?'));
  if (isApi) {
    const backendUrl = new URL(url.pathname + url.search, 'https://curve-metrics-platform.onrender.com');
    const headers = new Headers(context.request.headers);
    headers.set('X-Forwarded-Host', url.host);
    
    const init = {
      method: context.request.method,
      headers: headers,
      body: ['GET', 'HEAD'].includes(context.request.method) ? undefined : context.request.body,
      redirect: 'manual'
    };
    return fetch(backendUrl.toString(), init);
  }
  return context.next();
}
