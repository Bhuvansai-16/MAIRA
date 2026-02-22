import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { User, Session, AuthError } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

interface AuthContextType {
    user: User | null;
    session: Session | null;
    loading: boolean;
    signInWithEmail: (email: string, password: string) => Promise<{ error: AuthError | null }>;
    signUpWithEmail: (email: string, password: string, fullName?: string) => Promise<{ error: AuthError | null }>;
    signInWithGoogle: () => Promise<{ error: AuthError | null }>;
    signInWithGithub: () => Promise<{ error: AuthError | null }>;
    signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

interface AuthProviderProps {
    children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
    const [user, setUser] = useState<User | null>(null);
    const [session, setSession] = useState<Session | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // Get initial session
        const getInitialSession = async () => {
            try {
                const { data: { session }, error } = await supabase.auth.getSession();
                if (error) {
                    console.error('Error getting session:', error);
                } else {
                    setSession(session);
                    setUser(session?.user ?? null);

                    // Sync user on initial load if session exists
                    if (session?.user) {
                        try {
                            await syncUserToBackend(session.user);
                        } catch (error) {
                            console.warn('Failed to sync user on initial load:', error);
                        }
                    }
                }
            } catch (error) {
                console.error('Error in getInitialSession:', error);
            } finally {
                setLoading(false);
            }
        };

        getInitialSession();

        // Listen for auth changes
        const { data: { subscription } } = supabase.auth.onAuthStateChange(
            async (event, session) => {
                console.log('Auth state changed:', event, session?.user?.email);
                setSession(session);
                setUser(session?.user ?? null);
                setLoading(false);

                // Sync user to backend's users table when they sign in
                if (event === 'SIGNED_IN' && session?.user) {
                    try {
                        await syncUserToBackend(session.user);
                    } catch (error) {
                        console.warn('Failed to sync user to backend:', error);
                    }
                }
            }
        );

        return () => {
            subscription.unsubscribe();
        };
    }, []);

    // Sync user data to our users table via backend API
    const syncUserToBackend = async (user: User) => {
        try {
            const response = await axios.post(`${API_BASE}/users/sync`, {
                user_id: user.id,
                email: user.email,
                display_name: user.user_metadata?.full_name || user.user_metadata?.name || user.email?.split('@')[0],
                avatar_url: user.user_metadata?.avatar_url,
                auth_provider: user.app_metadata?.provider || 'email',
            });

            if (response.data.success) {
                console.log('✅ User synced to backend:', response.data);
            }
        } catch (error) {
            console.error('Error syncing user to backend:', error);
            throw error;
        }
    };

    const signInWithEmail = useCallback(async (email: string, password: string) => {
        const { error } = await supabase.auth.signInWithPassword({
            email,
            password,
        });
        return { error };
    }, []);

    const signUpWithEmail = useCallback(async (email: string, password: string, fullName?: string) => {
        const { error } = await supabase.auth.signUp({
            email,
            password,
            options: {
                data: {
                    full_name: fullName,
                },
            },
        });
        return { error };
    }, []);

    const signInWithGoogle = useCallback(async () => {
        const { error } = await supabase.auth.signInWithOAuth({
            provider: 'google',
            options: {
                redirectTo: `${window.location.origin}/`,
            },
        });
        return { error };
    }, []);

    const signInWithGithub = useCallback(async () => {
        const { error } = await supabase.auth.signInWithOAuth({
            provider: 'github',
            options: {
                redirectTo: `${window.location.origin}/`,
            },
        });
        return { error };
    }, []);

    const signOut = useCallback(async () => {
        await supabase.auth.signOut();
        // Clear any local storage items
        localStorage.removeItem('maira_current_thread_id');
    }, []);

    return (
        <AuthContext.Provider
            value={{
                user,
                session,
                loading,
                signInWithEmail,
                signUpWithEmail,
                signInWithGoogle,
                signInWithGithub,
                signOut,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};
