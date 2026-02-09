import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://pteanoqxjpdumsazcalr.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB0ZWFub3F4anBkdW1zYXpjYWxyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk3ODQ2MjYsImV4cCI6MjA4NTM2MDYyNn0.zIvBdFuB0L6yLNHWEo6YxyctLRHNkVerq8jpVDGioZw';

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
    },
});

export type AuthUser = {
    id: string;
    email: string | undefined;
    user_metadata: {
        full_name?: string;
        avatar_url?: string;
        name?: string;
    };
};
