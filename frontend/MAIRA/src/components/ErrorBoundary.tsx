import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { logger, IS_PRODUCTION } from '../lib/config';

interface Props {
    children: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = {
            hasError: false,
            error: null,
            errorInfo: null
        };
    }

    static getDerivedStateFromError(error: Error): Partial<State> {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        this.setState({ errorInfo });
        
        // Log error to console (and potentially to error tracking service)
        logger.error('ErrorBoundary caught an error:', error, errorInfo);
        
        // In production, you could send this to an error tracking service
        if (IS_PRODUCTION) {
            // Example: sendToErrorTracking(error, errorInfo);
        }
    }

    handleRetry = () => {
        this.setState({ hasError: false, error: null, errorInfo: null });
    };

    handleGoHome = () => {
        window.location.href = '/';
    };

    handleRefresh = () => {
        window.location.reload();
    };

    render() {
        if (this.state.hasError) {
            if (this.props.fallback) {
                return this.props.fallback;
            }

            return (
                <div className="min-h-screen bg-black flex items-center justify-center p-6">
                    <div className="max-w-md w-full">
                        {/* Error Card */}
                        <div className="bg-[#0A0A0A] border border-red-500/20 rounded-2xl p-8 text-center shadow-2xl shadow-red-900/10">
                            {/* Icon */}
                            <div className="flex justify-center mb-6">
                                <div className="h-16 w-16 rounded-2xl bg-red-500/10 flex items-center justify-center">
                                    <AlertTriangle className="h-8 w-8 text-red-500" />
                                </div>
                            </div>

                            {/* Title */}
                            <h1 className="text-xl font-bold text-white mb-2">
                                Something went wrong
                            </h1>
                            
                            {/* Description */}
                            <p className="text-sm text-neutral-400 mb-6">
                                An unexpected error occurred. You can try refreshing the page or return to the home page.
                            </p>

                            {/* Error Details (Development only) */}
                            {!IS_PRODUCTION && this.state.error && (
                                <div className="mb-6 p-4 bg-red-500/5 border border-red-500/10 rounded-xl text-left">
                                    <p className="text-xs text-red-400 font-mono break-all">
                                        {this.state.error.message}
                                    </p>
                                    {this.state.errorInfo && (
                                        <details className="mt-2">
                                            <summary className="text-xs text-neutral-500 cursor-pointer hover:text-neutral-400">
                                                Stack trace
                                            </summary>
                                            <pre className="mt-2 text-[10px] text-neutral-600 overflow-auto max-h-32">
                                                {this.state.errorInfo.componentStack}
                                            </pre>
                                        </details>
                                    )}
                                </div>
                            )}

                            {/* Actions */}
                            <div className="flex flex-col gap-3">
                                <button
                                    onClick={this.handleRefresh}
                                    className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 transition-all"
                                >
                                    <RefreshCw size={16} />
                                    Refresh Page
                                </button>
                                
                                <button
                                    onClick={this.handleGoHome}
                                    className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-neutral-300 font-semibold hover:bg-white/10 transition-all"
                                >
                                    <Home size={16} />
                                    Go to Home
                                </button>
                            </div>
                        </div>

                        {/* Footer */}
                        <p className="text-center text-xs text-neutral-600 mt-6">
                            If this problem persists, please contact support.
                        </p>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
