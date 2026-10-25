type Environment = Record<string, string | undefined>;

export function readSupabaseConfig(env: Environment) {
  const url = env.VITE_SUPABASE_URL?.trim();
  const key = env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim() || env.VITE_SUPABASE_ANON_KEY?.trim();
  if (!url || !key || url.includes('YOUR_PROJECT')) return null;
  return { url, key };
}
