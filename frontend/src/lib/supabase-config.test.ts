import { describe, expect, it } from 'vitest';
import { readSupabaseConfig } from './supabase-config';

describe('Supabase environment names', () => {
  const url = 'https://example.supabase.co';
  it('supports the publishable key setting', () => {
    expect(readSupabaseConfig({VITE_SUPABASE_URL:url,VITE_SUPABASE_PUBLISHABLE_KEY:'test-public-key'})).toEqual({url,key:'test-public-key'});
  });
  it('supports the existing anon key setting', () => {
    expect(readSupabaseConfig({VITE_SUPABASE_URL:url,VITE_SUPABASE_ANON_KEY:'test-public-key'})).toEqual({url,key:'test-public-key'});
  });
  it('prefers a publishable key when both settings exist', () => {
    expect(readSupabaseConfig({VITE_SUPABASE_URL:url,VITE_SUPABASE_PUBLISHABLE_KEY:'preferred',VITE_SUPABASE_ANON_KEY:'legacy'})?.key).toBe('preferred');
  });
  it('trims values and falls back when the primary setting is blank', () => {
    expect(readSupabaseConfig({VITE_SUPABASE_URL:` ${url} `,VITE_SUPABASE_PUBLISHABLE_KEY:' ',VITE_SUPABASE_ANON_KEY:' test-public-key '})).toEqual({url,key:'test-public-key'});
  });
  it('requires a URL and key', () => {
    expect(readSupabaseConfig({VITE_SUPABASE_URL:url})).toBeNull();
    expect(readSupabaseConfig({VITE_SUPABASE_ANON_KEY:'test-public-key'})).toBeNull();
  });
});
