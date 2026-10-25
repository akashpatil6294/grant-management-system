import { supabase } from '../lib/supabase';
export type Entity = { id: string; [key: string]: string | boolean | null };
export const text = (row: Entity, key: string) => String(row[key] ?? '');
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const { data } = supabase ? await supabase.auth.getSession() : { data: { session: null } };
  if (!data.session) throw new Error('Please sign in to continue.');
  let response: Response;
  try {
    response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api${path}`, {
      method, headers: { Authorization: `Bearer ${data.session.access_token}`, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(20000),
    });
  } catch { throw new Error('Cannot reach the API. Check that the backend is running, then try again.'); }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new Error(Array.isArray(detail) ? detail.map((e: {loc: string[]; msg: string}) => `${e.loc.slice(1).join('.')}: ${e.msg}`).join('; ') : detail || `Request failed (${response.status}).`);
  }
  return payload as T;
}

export async function allPages(path: string): Promise<Entity[]> {
  const rows: Entity[] = [];
  for (let offset = 0; ; offset += 500) {
    const page = await api<Entity[]>(`${path}${path.includes('?') ? '&' : '?'}limit=500&offset=${offset}`);
    rows.push(...page);
    if (page.length < 500) return rows;
  }
}
