import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const SUPABASE_URL = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").trim();
const SUPABASE_PUBLISHABLE_KEY = (process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "").trim();

let browserClient: SupabaseClient | null = null;

export function hasSupabaseBrowserConfig(): boolean {
  return Boolean(SUPABASE_URL && SUPABASE_PUBLISHABLE_KEY);
}

export function getSupabaseBrowserClient(): SupabaseClient | null {
  if (!hasSupabaseBrowserConfig()) {
    return null;
  }

  if (!browserClient) {
    browserClient = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    });
  }

  return browserClient;
}
