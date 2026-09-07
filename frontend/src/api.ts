// Only this public URL is included in the Pages bundle. Credentials stay in memory.
const configured = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || '';
if (configured && !/^https:\/\//.test(configured) && !/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(configured)) {
  throw new Error('The journal API must use HTTPS.');
}
export const remoteApi = Boolean(configured);
let authorization = '';
export function setCredentials(user: string, password: string) {
  const bytes = new TextEncoder().encode(`${user}:${password}`);
  authorization = `Basic ${btoa(String.fromCharCode(...bytes))}`;
}
export function clearCredentials() { authorization = ''; }
async function request(path: string, options?: RequestInit) {
  const headers = new Headers(options?.headers);
  if (authorization) headers.set('Authorization', authorization);
  const response = await fetch(`${configured}/api/${path}`, {
    ...options, headers, credentials: remoteApi ? 'omit' : 'same-origin', cache: 'no-store',
  });
  if (!response.ok) {
    if (response.status === 401 && remoteApi) window.dispatchEvent(new Event('journal:sign-out'));
    let detail = `Request failed (${response.status})`;
    try { detail = (await response.json()).detail || detail; } catch { /* Keep status. */ }
    throw new Error(detail);
  }
  return response;
}
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  return (await request(path, options)).json();
}
export async function downloadCalls() {
  const response = await request('export.csv');
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url; link.download = 'nifty-signal-calls.csv'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
