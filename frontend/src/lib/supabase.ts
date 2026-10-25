import { createClient } from '@supabase/supabase-js';
import { readSupabaseConfig } from './supabase-config';
const config = readSupabaseConfig(import.meta.env);
export const supabase = config ? createClient(config.url, config.key) : null;
