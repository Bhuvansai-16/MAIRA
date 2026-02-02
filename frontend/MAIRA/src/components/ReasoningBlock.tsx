import { useState } from 'react';
import { ChevronDown, ChevronUp, Brain, Sparkles } from 'lucide-react';
import { cn } from '../lib/utils';

interface ReasoningBlockProps {
    content: string;
    isStreaming?: boolean;
    className?: string;
}

export const ReasoningBlock = ({ content, isStreaming = false, className }: ReasoningBlockProps) => {
    const [isExpanded, setIsExpanded] = useState(false);

    if (!content) return null;

    // Split content into lines for better display
    const lines = content.split('\n').filter(line => line.trim());
    const previewLines = lines.slice(0, 2);
    const hasMore = lines.length > 2;

    return (
        <div className={cn(
            "rounded-xl border transition-all duration-300 overflow-hidden",
            isStreaming 
                ? "border-purple-500/30 bg-purple-500/5 animate-pulse" 
                : "border-white/10 bg-white/5",
            isExpanded ? "shadow-lg shadow-purple-500/10" : "",
            className
        )}>
            {/* Header */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-white/5 transition-colors"
            >
                <div className="flex items-center gap-2">
                    <div className={cn(
                        "flex h-7 w-7 items-center justify-center rounded-lg transition-all",
                        isStreaming 
                            ? "bg-purple-500/20 text-purple-400" 
                            : "bg-white/10 text-neutral-400"
                    )}>
                        {isStreaming ? (
                            <Sparkles size={14} className="animate-pulse" />
                        ) : (
                            <Brain size={14} />
                        )}
                    </div>
                    <span className={cn(
                        "text-[10px] font-bold uppercase tracking-widest",
                        isStreaming ? "text-purple-400" : "text-neutral-500"
                    )}>
                        {isStreaming ? "Thinking..." : "Reasoning"}
                    </span>
                </div>
                <div className="flex items-center gap-2 text-neutral-500">
                    {!isStreaming && (
                        <>
                            <span className="text-[10px] font-medium">
                                {lines.length} step{lines.length !== 1 ? 's' : ''}
                            </span>
                            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </>
                    )}
                </div>
            </button>

            {/* Content */}
            <div className={cn(
                "transition-all duration-300 ease-out",
                isExpanded || isStreaming ? "max-h-[500px]" : "max-h-0"
            )}>
                <div className="px-4 pb-4 pt-1 border-t border-white/5">
                    {/* Streaming or Expanded Content */}
                    {(isExpanded || isStreaming) && (
                        <div className="space-y-2">
                            {lines.map((line, idx) => (
                                <div 
                                    key={idx}
                                    className={cn(
                                        "flex items-start gap-2 text-xs animate-fade-in",
                                        isStreaming && idx === lines.length - 1 ? "text-purple-300" : "text-neutral-400"
                                    )}
                                >
                                    <span className={cn(
                                        "flex h-5 w-5 shrink-0 items-center justify-center rounded text-[10px] font-bold",
                                        isStreaming && idx === lines.length - 1 
                                            ? "bg-purple-500/20 text-purple-400" 
                                            : "bg-white/10 text-neutral-500"
                                    )}>
                                        {idx + 1}
                                    </span>
                                    <span className="leading-relaxed pt-0.5">{line}</span>
                                </div>
                            ))}
                            {isStreaming && (
                                <div className="flex items-center gap-2 pt-2">
                                    <div className="flex gap-1">
                                        <div className="h-1.5 w-1.5 rounded-full bg-purple-500 animate-bounce [animation-delay:-0.3s]" />
                                        <div className="h-1.5 w-1.5 rounded-full bg-purple-500 animate-bounce [animation-delay:-0.15s]" />
                                        <div className="h-1.5 w-1.5 rounded-full bg-purple-500 animate-bounce" />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Preview (when collapsed and not streaming) */}
            {!isExpanded && !isStreaming && hasMore && (
                <div className="px-4 pb-3">
                    <div className="text-xs text-neutral-500 truncate">
                        {previewLines.join(' • ')}
                        {hasMore && <span className="text-neutral-600"> ...</span>}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ReasoningBlock;
