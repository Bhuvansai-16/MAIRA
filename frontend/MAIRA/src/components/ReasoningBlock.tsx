import { useState, useEffect, useRef, useCallback } from 'react';
import { ChevronDown, ChevronUp, Brain, Sparkles, Clock, Hash, Zap } from 'lucide-react';
import { cn } from '../lib/utils';

interface ReasoningBlockProps {
    content: string;
    isStreaming?: boolean;
    className?: string;
}

// ─── tiny helpers ────────────────────────────────────────────────────────────

/** Count approximate tokens (words ÷ 0.75) */
const approxTokens = (text: string) =>
    Math.round(text.trim().split(/\s+/).filter(Boolean).length / 0.75);

/** Format elapsed seconds as m:ss or :ss */
const fmtTime = (secs: number) => {
    if (secs < 60) return `${secs}s`;
    return `${Math.floor(secs / 60)}m ${secs % 60}s`;
};

/** Quick parse of the content to detect labelled thought steps */
function parseSteps(raw: string): { label: string | null; body: string }[] {
    const lines = raw.split('\n');
    const steps: { label: string | null; body: string }[] = [];
    let current: { label: string | null; body: string } | null = null;

    for (const line of lines) {
        // Match "Step N:", numbered list "1.", or "Phase N:" prefixes
        const stepMatch = line.match(/^(Step\s*\d+[:.]|Phase\s*\d+[:.]|\d+\.)\s*(.*)/i);
        if (stepMatch) {
            if (current) steps.push(current);
            current = { label: stepMatch[1].replace(/\.$/, ':'), body: stepMatch[2] };
        } else if (line.trim()) {
            if (current) {
                current.body += (current.body ? ' ' : '') + line.trim();
            } else {
                current = { label: null, body: line.trim() };
            }
        }
    }
    if (current) steps.push(current);
    return steps.filter(s => s.body.trim());
}

// ─── component ───────────────────────────────────────────────────────────────

export const ReasoningBlock = ({ content, isStreaming = false, className }: ReasoningBlockProps) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [elapsedSecs, setElapsedSecs] = useState(0);
    const [displayedContent, setDisplayedContent] = useState('');
    const [hasAutoExpanded, setHasAutoExpanded] = useState(false);
    const scrollRef = useRef<HTMLDivElement>(null);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const startTimeRef = useRef<number | null>(null);

    // ── auto-expand when streaming starts ──
    useEffect(() => {
        if (isStreaming && content && !hasAutoExpanded) {
            setIsExpanded(true);
            setHasAutoExpanded(true);
        }
    }, [isStreaming, content, hasAutoExpanded]);

    // ── collapse after streaming finishes ──
    useEffect(() => {
        // intentional: user keeps expanded state after streaming ends
    }, [isStreaming, hasAutoExpanded]);

    // ── elapsed timer while streaming ──
    useEffect(() => {
        if (isStreaming) {
            if (!startTimeRef.current) startTimeRef.current = Date.now();
            timerRef.current = setInterval(() => {
                setElapsedSecs(Math.floor((Date.now() - startTimeRef.current!) / 1000));
            }, 1000);
        } else {
            if (timerRef.current) clearInterval(timerRef.current);
        }
        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [isStreaming]);

    // ── sync displayed content ──
    useEffect(() => {
        setDisplayedContent(content);
    }, [content]);

    // ── auto-scroll to bottom while streaming ──
    const autoScroll = useCallback(() => {
        if (isStreaming && scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [isStreaming]);

    useEffect(() => {
        autoScroll();
    }, [displayedContent, autoScroll]);

    if (!content) return null;

    const steps = parseSteps(displayedContent);
    const tokens = approxTokens(displayedContent);
    const wordCount = displayedContent.trim().split(/\s+/).filter(Boolean).length;

    return (
        <div
            className={cn(
                'relative rounded-2xl overflow-hidden transition-all duration-500 mb-3',
                'border shadow-lg',
                isStreaming
                    ? 'border-violet-500/25 bg-gradient-to-br from-violet-950/40 via-[#0f0a1e]/60 to-indigo-950/30 shadow-violet-500/10'
                    : 'border-white/8 bg-gradient-to-br from-white/[0.03] to-transparent shadow-black/20',
                isExpanded && !isStreaming && 'border-white/12',
                className
            )}
            style={{ backdropFilter: 'blur(12px)' }}
        >
            {/* ── animated top gradient bar ── */}
            {isStreaming && (
                <div className="absolute top-0 left-0 right-0 h-[2px] overflow-hidden rounded-t-2xl">
                    <div
                        className="h-full w-[60%] rounded-full"
                        style={{
                            background: 'linear-gradient(90deg, transparent, #8b5cf6, #a78bfa, #8b5cf6, transparent)',
                            animation: 'shimmer 2s infinite linear',
                            backgroundSize: '200% 100%',
                        }}
                    />
                </div>
            )}

            {/* ── header ── */}
            <button
                onClick={() => setIsExpanded(e => !e)}
                className={cn(
                    'w-full px-4 py-3 flex items-center justify-between',
                    'hover:bg-white/[0.03] transition-colors duration-200 cursor-pointer',
                )}
                aria-expanded={isExpanded}
            >
                {/* Left: icon + label */}
                <div className="flex items-center gap-3">
                    {/* Icon orb */}
                    <div
                        className={cn(
                            'relative flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-all duration-500',
                            isStreaming
                                ? 'bg-violet-500/20 text-violet-300'
                                : 'bg-white/8 text-neutral-400'
                        )}
                    >
                        {isStreaming ? (
                            <>
                                <Sparkles size={14} className="animate-pulse" />
                                {/* pulse ring */}
                                <span className="absolute inset-0 rounded-xl animate-ping bg-violet-500/20" />
                            </>
                        ) : (
                            <Brain size={14} />
                        )}
                    </div>

                    {/* Title + sub-label */}
                    <div className="flex flex-col items-start">
                        <span className={cn(
                            'text-[11px] font-bold uppercase tracking-widest leading-none',
                            isStreaming ? 'text-violet-300' : 'text-neutral-400'
                        )}>
                            {isStreaming ? 'Thinking' : 'Reasoning Trace'}
                        </span>
                        {isStreaming && (
                            <span className="text-[9px] text-violet-400/60 tracking-wide mt-0.5 leading-none">
                                Processing your request...
                            </span>
                        )}
                    </div>
                </div>

                {/* Right: stats + chevron */}
                <div className="flex items-center gap-3 text-neutral-500">
                    {/* Token count */}
                    <div className="hidden sm:flex items-center gap-1 text-[10px]">
                        <Hash size={9} />
                        <span>{tokens.toLocaleString()} tokens</span>
                    </div>

                    {/* Word count */}
                    <div className="hidden sm:flex items-center gap-1 text-[10px]">
                        <Zap size={9} />
                        <span>{wordCount} words</span>
                    </div>

                    {/* Elapsed time when streaming */}
                    {isStreaming && (
                        <div className="flex items-center gap-1 text-[10px] text-violet-400/70">
                            <Clock size={9} />
                            <span className="tabular-nums">{fmtTime(elapsedSecs)}</span>
                        </div>
                    )}

                    {/* Step count when done */}
                    {!isStreaming && steps.length > 0 && (
                        <span className="text-[10px] font-medium">
                            {steps.length} step{steps.length !== 1 ? 's' : ''}
                        </span>
                    )}

                    {/* Chevron */}
                    <div className={cn(
                        'transition-transform duration-300',
                        isExpanded ? 'rotate-0' : 'rotate-0'
                    )}>
                        {isExpanded
                            ? <ChevronUp size={14} />
                            : <ChevronDown size={14} />
                        }
                    </div>
                </div>
            </button>

            {/* ── expandable body ── */}
            <div
                className={cn(
                    'grid transition-all duration-500 ease-in-out',
                    isExpanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
                )}
            >
                <div className="overflow-hidden">
                    <div className="border-t border-white/[0.06] px-4 pb-4 pt-3">
                        {/* Scrollable content area */}
                        <div
                            ref={scrollRef}
                            className={cn(
                                'overflow-y-auto pr-1 space-y-1.5 text-xs leading-relaxed',
                                'scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent',
                                isStreaming ? 'max-h-64' : 'max-h-80'
                            )}
                        >
                            {steps.length > 0 ? (
                                // Structured step-by-step view
                                steps.map((step, idx) => {
                                    const isLast = idx === steps.length - 1;
                                    const isActive = isStreaming && isLast;
                                    return (
                                        <div
                                            key={idx}
                                            className={cn(
                                                'flex items-start gap-2.5 rounded-xl px-3 py-2 transition-all duration-300',
                                                isActive
                                                    ? 'bg-violet-500/10 border border-violet-500/20'
                                                    : idx % 2 === 0
                                                        ? 'bg-white/[0.02]'
                                                        : 'bg-transparent'
                                            )}
                                        >
                                            {/* Step badge */}
                                            <div className={cn(
                                                'flex h-5 min-w-[20px] items-center justify-center rounded-md text-[9px] font-black shrink-0 mt-0.5',
                                                isActive
                                                    ? 'bg-violet-500/30 text-violet-300'
                                                    : 'bg-white/8 text-neutral-500'
                                            )}>
                                                {step.label ? (
                                                    <span>{idx + 1}</span>
                                                ) : (
                                                    <span className="opacity-60">·</span>
                                                )}
                                            </div>

                                            {/* Content */}
                                            <div className="flex-1 min-w-0">
                                                {step.label && (
                                                    <span className={cn(
                                                        'text-[9px] font-black uppercase tracking-widest mr-2',
                                                        isActive ? 'text-violet-400' : 'text-neutral-600'
                                                    )}>
                                                        {step.label}
                                                    </span>
                                                )}
                                                <span className={cn(
                                                    'break-words',
                                                    isActive ? 'text-violet-200/90' : 'text-neutral-400'
                                                )}>
                                                    {step.body}
                                                    {isActive && (
                                                        <span className="inline-block ml-1 w-1.5 h-3.5 bg-violet-400/80 rounded-sm animate-pulse align-middle" />
                                                    )}
                                                </span>
                                            </div>
                                        </div>
                                    );
                                })
                            ) : (
                                // Plain text fallback (no detectable steps)
                                <div className={cn(
                                    'rounded-xl px-3 py-2 whitespace-pre-wrap break-words',
                                    isStreaming ? 'text-violet-200/80' : 'text-neutral-400'
                                )}>
                                    {displayedContent}
                                    {isStreaming && (
                                        <span className="inline-block ml-1 w-1.5 h-3.5 bg-violet-400/80 rounded-sm animate-pulse align-middle" />
                                    )}
                                </div>
                            )}
                        </div>

                        {/* ── streaming footer ── */}
                        {isStreaming && (
                            <div className="mt-3 pt-2.5 border-t border-violet-500/10 flex items-center justify-between">
                                {/* Pulse dots */}
                                <div className="flex gap-1 items-center">
                                    <div className="h-1.5 w-1.5 rounded-full bg-violet-500 animate-bounce [animation-delay:-0.3s]" />
                                    <div className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-bounce [animation-delay:-0.15s]" />
                                    <div className="h-1.5 w-1.5 rounded-full bg-violet-300 animate-bounce" />
                                    <span className="ml-2 text-[10px] text-violet-400/60 font-medium">Generating reasoning...</span>
                                </div>
                                {/* Live token counter */}
                                <span className="text-[10px] text-violet-500/50 tabular-nums">
                                    ~{tokens.toLocaleString()} tokens
                                </span>
                            </div>
                        )}

                        {/* ── done footer ── */}
                        {!isStreaming && (
                            <div className="mt-3 pt-2.5 border-t border-white/[0.05] flex items-center gap-2 text-[10px] text-neutral-600">
                                <Brain size={9} />
                                <span>Reasoning completed · {steps.length} step{steps.length !== 1 ? 's' : ''} · ~{tokens.toLocaleString()} tokens · {wordCount} words</span>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* ── collapsed preview when not expanded and done ── */}
            {!isExpanded && !isStreaming && content && (
                <div className="px-4 pb-3 -mt-1">
                    <div className="text-[10px] text-neutral-600 line-clamp-1 italic">
                        {displayedContent.trim().split('\n')[0]?.substring(0, 120)}
                        {displayedContent.length > 120 && '…'}
                    </div>
                </div>
            )}

            {/* Shimmer keyframe (injected inline once) */}
            <style>{`
                @keyframes shimmer {
                    0%   { transform: translateX(-100%); }
                    100% { transform: translateX(250%); }
                }
                .scrollbar-thin::-webkit-scrollbar { width: 4px; }
                .scrollbar-thin::-webkit-scrollbar-track { background: transparent; }
                .scrollbar-thin::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 999px; }
            `}</style>
        </div>
    );
};

export default ReasoningBlock;
