import { useState, useEffect } from 'react';
import { Wifi, WifiOff, RefreshCw } from 'lucide-react';
import { cn } from '../lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

interface ConnectionStatusProps {
    className?: string;
}

export const ConnectionStatus = ({ className }: ConnectionStatusProps) => {
    const [isOnline, setIsOnline] = useState(navigator.onLine);
    const [showBanner, setShowBanner] = useState(false);
    const [isReconnecting, setIsReconnecting] = useState(false);

    useEffect(() => {
        const handleOnline = () => {
            setIsOnline(true);
            setIsReconnecting(false);
            // Show "back online" banner briefly
            setShowBanner(true);
            setTimeout(() => setShowBanner(false), 3000);
        };

        const handleOffline = () => {
            setIsOnline(false);
            setShowBanner(true);
        };

        window.addEventListener('online', handleOnline);
        window.addEventListener('offline', handleOffline);

        return () => {
            window.removeEventListener('online', handleOnline);
            window.removeEventListener('offline', handleOffline);
        };
    }, []);

    const handleRetry = () => {
        setIsReconnecting(true);
        // Try to fetch something to check connection
        fetch('/api/health', { method: 'HEAD' })
            .then(() => {
                setIsOnline(true);
                setIsReconnecting(false);
                setShowBanner(false);
            })
            .catch(() => {
                setIsReconnecting(false);
            });
    };

    // Don't show anything if online and banner is hidden
    if (isOnline && !showBanner) {
        return null;
    }

    return (
        <AnimatePresence>
            {showBanner && (
                <motion.div
                    initial={{ y: -100, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: -100, opacity: 0 }}
                    transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                    className={cn(
                        "fixed top-0 left-0 right-0 z-[100] flex items-center justify-center gap-3 px-4 py-3",
                        isOnline 
                            ? "bg-green-500/10 border-b border-green-500/20" 
                            : "bg-red-500/10 border-b border-red-500/20",
                        className
                    )}
                >
                    {/* Icon */}
                    <div className={cn(
                        "flex h-8 w-8 items-center justify-center rounded-lg",
                        isOnline ? "bg-green-500/20" : "bg-red-500/20"
                    )}>
                        {isOnline ? (
                            <Wifi size={16} className="text-green-500" />
                        ) : (
                            <WifiOff size={16} className="text-red-500" />
                        )}
                    </div>

                    {/* Message */}
                    <span className={cn(
                        "text-sm font-semibold",
                        isOnline ? "text-green-400" : "text-red-400"
                    )}>
                        {isOnline 
                            ? "You're back online!" 
                            : "You're offline. Check your connection."}
                    </span>

                    {/* Retry button (offline only) */}
                    {!isOnline && (
                        <button
                            onClick={handleRetry}
                            disabled={isReconnecting}
                            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/10 text-white text-xs font-semibold hover:bg-white/20 transition-all disabled:opacity-50"
                        >
                            <RefreshCw size={12} className={cn(isReconnecting && "animate-spin")} />
                            {isReconnecting ? 'Checking...' : 'Retry'}
                        </button>
                    )}

                    {/* Close button (online only) */}
                    {isOnline && (
                        <button
                            onClick={() => setShowBanner(false)}
                            className="ml-2 text-green-400/60 hover:text-green-400 transition-colors"
                        >
                            ✕
                        </button>
                    )}
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default ConnectionStatus;
