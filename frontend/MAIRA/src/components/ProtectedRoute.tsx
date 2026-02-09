import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Loader2, Shield } from 'lucide-react';
import type { ReactNode } from 'react';

interface ProtectedRouteProps {
    children: ReactNode;
}

export const ProtectedRoute = ({ children }: ProtectedRouteProps) => {
    const { user, loading } = useAuth();

    if (loading) {
        return (
            <div className="min-h-screen bg-[#080808] flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <div className="relative">
                        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600 to-indigo-600 shadow-2xl shadow-violet-500/20">
                            <Shield className="h-8 w-8 text-white" />
                        </div>
                        <div className="absolute -bottom-1 -right-1">
                            <Loader2 className="h-6 w-6 text-violet-400 animate-spin" />
                        </div>
                    </div>
                    <p className="text-sm text-neutral-400 font-medium">Loading...</p>
                </div>
            </div>
        );
    }

    if (!user) {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
};
