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
            "flex flex-col items-center justify-center bg-black",
            fullScreen ? "min-h-screen" : "h-full w-full py-20"
        )}>
            {/* Animated Logo */}
            <div className="relative mb-8">
                {/* Outer glow ring */}
                <div className="absolute inset-0 rounded-3xl bg-blue-500/20 blur-xl animate-pulse" />
                
                {/* Logo container */}
                <div className="relative flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-blue-600 to-blue-500 shadow-2xl shadow-blue-500/30">
                    <Shield className="h-10 w-10 text-white animate-pulse" />
                </div>
                
                {/* Spinning ring */}
                <div className="absolute -inset-2 rounded-[28px] border-2 border-transparent border-t-blue-500/50 animate-spin" 
                     style={{ animationDuration: '2s' }} />
            </div>

            {/* App name */}
            <h1 className="text-2xl font-black text-white tracking-tight mb-2">
                MAIRA
            </h1>
            
            {/* Loading message */}
            <p className="text-sm text-neutral-500 font-medium">
                {message}
            </p>

            {/* Loading dots */}
            <div className="flex gap-1.5 mt-6">
                <div className="h-2 w-2 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.3s]" />
                <div className="h-2 w-2 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.15s]" />
                <div className="h-2 w-2 rounded-full bg-blue-500 animate-bounce" />
            </div>
        </div>
    );
};

export default LoadingScreen;
