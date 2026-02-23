import { Shield } from 'lucide-react';
import { cn } from '../lib/utils';

interface LoadingScreenProps {
    message?: string;
    fullScreen?: boolean;
}

export const LoadingScreen = ({
    message = 'Loading...',
    fullScreen = true
}: LoadingScreenProps) => {
    return (
        <div className={cn(
            "flex flex-col items-center justify-center bg-black overflow-hidden relative",
            fullScreen ? "min-h-screen" : "h-full w-full py-20"
        )}>
            {/* Ambient background glows */}
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-[120px] animate-pulse" />
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-violet-600/10 rounded-full blur-[120px] animate-pulse [animation-delay:1s]" />

            {/* Animated Logo Container */}
            <div className="relative mb-12">
                {/* Outer rotating halo */}
                <div className="absolute -inset-8 rounded-full border border-blue-500/10 animate-[spin_8s_linear_infinite]" />
                <div className="absolute -inset-12 rounded-full border border-violet-500/5 animate-[spin_12s_linear_infinite_reverse]" />

                {/* Logo with glassmorphism */}
                <div className="relative flex h-24 w-24 items-center justify-center rounded-[32px] bg-white/[0.03] border border-white/10 backdrop-blur-xl shadow-2xl overflow-hidden group">
                    {/* Inner gradient glow */}
                    <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 to-violet-600/20 opacity-50 transition-opacity group-hover:opacity-100" />

                    {/* Icon */}
                    <Shield className="h-12 w-12 text-blue-500 drop-shadow-[0_0_15px_rgba(59,130,246,0.5)] animate-pulse" />

                    {/* Shimmer effect */}
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent -translate-x-full animate-[shimmer_2s_infinite]" />
                </div>

                {/* Orbiting particles */}
                <div className="absolute top-0 left-0 w-full h-full animate-[spin_4s_linear_infinite]">
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 h-2 w-2 rounded-full bg-blue-400 blur-[2px]" />
                </div>
            </div>

            {/* App name with refined typography */}
            <div className="flex flex-col items-center gap-1 z-10 text-center">
                <h1 className="text-3xl font-black text-white tracking-[0.2em] mb-4 relative">
                    MAIRA
                    <span className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-12 h-1 bg-gradient-to-r from-blue-600 to-violet-600 rounded-full" />
                </h1>

                {/* Loading message */}
                <p className="text-sm text-neutral-400 font-medium tracking-wide uppercase opacity-70">
                    {message}
                </p>

                {/* Modern progress indicator */}
                <div className="flex gap-2 mt-8">
                    {[0, 1, 2].map((i) => (
                        <div
                            key={i}
                            className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-bounce"
                            style={{ animationDelay: `${i * 0.15}s` }}
                        />
                    ))}
                </div>
            </div>

            <style>{`
                @keyframes shimmer {
                    100% { transform: translateX(100%); }
                }
            `}</style>
        </div>
    );
};

export default LoadingScreen;
