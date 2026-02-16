import { useState, useEffect, useRef } from 'react';
import { Sparkles, Search, BookOpen, FileText, CheckCircle2, Brain } from 'lucide-react';
import { cn } from '../lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

interface DeepResearchProgressProps {
    status?: string;
    isActive: boolean;
    progress?: number;
}

// Reordered to match backend flow: Search -> Analyze -> Draft -> Reason/Verify -> Finalize
const RESEARCH_PHASES = [
    { label: 'Starting research', icon: Sparkles, color: 'from-amber-400 to-orange-500', duration: 8 },
    { label: 'Searching sources', icon: Search, color: 'from-blue-400 to-cyan-500', duration: 15 },
    { label: 'Analyzing papers', icon: BookOpen, color: 'from-purple-400 to-violet-500', duration: 20 },
    { label: 'Drafting report', icon: FileText, color: 'from-pink-400 to-rose-500', duration: 20 },
    { label: 'Deep verification', icon: Brain, color: 'from-emerald-400 to-green-500', duration: 25 },
    { label: 'Finalizing', icon: CheckCircle2, color: 'from-teal-400 to-cyan-500', duration: 12 },
];

export const DeepResearchProgress = ({ status, isActive, progress: explicitProgress }: DeepResearchProgressProps) => {
    const [progress, setProgress] = useState(0);
    const [currentPhaseIndex, setCurrentPhaseIndex] = useState(0);
    const [elapsed, setElapsed] = useState(0);
    const startTimeRef = useRef(Date.now());
    const animFrameRef = useRef<number>(0);

    // Determine phase from status text or auto-advance
    useEffect(() => {
        if (!isActive) return;

        if (status) {
            const lower = status.toLowerCase();
            // Phase 1: Search
            if (lower.includes('searching') || lower.includes('search') || lower.includes('web_search') || lower.includes('arxiv')) {
                setCurrentPhaseIndex(1);
            }
            // Phase 2: Analyze
            else if (lower.includes('analyz') || lower.includes('reading') || lower.includes('paper') || lower.includes('literature')) {
                setCurrentPhaseIndex(2);
            }
            // Phase 3: Drafting (Was 4)
            else if (lower.includes('draft') || lower.includes('writing') || lower.includes('generat')) {
                setCurrentPhaseIndex(3);
            }
            // Phase 4: Verification / Deep Reasoning (Was 3)
            // Includes typical verification tool keywords
            else if (
                lower.includes('reason') ||
                lower.includes('thinking') ||
                lower.includes('deep') ||
                lower.includes('validat') ||
                lower.includes('check') ||
                lower.includes('assess') ||
                lower.includes('refin')
            ) {
                setCurrentPhaseIndex(4);
            }
            // Phase 5: Finalizing (Report generation and final checks)
            // Includes "report" as that usually means report-subagent
            else if (lower.includes('final') || lower.includes('complet') || lower.includes('report') || lower.includes('done')) {
                setCurrentPhaseIndex(5);
            }
        }

        // Also update phase based on progress if status didn't catch it
        if (typeof explicitProgress === 'number' && explicitProgress > 0) {
            if (explicitProgress >= 90) setCurrentPhaseIndex(5); // Finalizing
            else if (explicitProgress >= 75) setCurrentPhaseIndex(4); // Verification
            else if (explicitProgress >= 60) setCurrentPhaseIndex(3); // Drafting
            else if (explicitProgress >= 40) setCurrentPhaseIndex(2); // Analysis (Papers)
            else if (explicitProgress >= 15) setCurrentPhaseIndex(1); // Searching
            else setCurrentPhaseIndex(0); // Starting
        }
    }, [status, isActive, explicitProgress]);

    // Handle progress updates (either explicit or simulated)
    useEffect(() => {
        if (!isActive) {
            setProgress(0);
            setElapsed(0);
            startTimeRef.current = Date.now();
            return;
        }

        // If backend provides explicit progress, use it directly (no simulation)
        if (typeof explicitProgress === 'number' && explicitProgress > 0) {
            setProgress(explicitProgress);
            return;
        }

        // Fallback: Simulated progress for smooth UX when no explicit updates
        const totalEstimated = RESEARCH_PHASES.reduce((sum, p) => sum + p.duration, 0); // ~100s total

        const tick = () => {
            const now = Date.now();
            const elapsedSec = (now - startTimeRef.current) / 1000;
            setElapsed(elapsedSec);

            // Asymptotic progress: fast at first, slows down near 95%
            // Never reaches 100% until actually done
            const rawProgress = 1 - Math.exp(-elapsedSec / (totalEstimated * 0.6));
            const cappedProgress = Math.min(rawProgress * 95, 95); // Cap at 95%

            setProgress(cappedProgress);
            animFrameRef.current = requestAnimationFrame(tick);
        };

        animFrameRef.current = requestAnimationFrame(tick);
        return () => {
            if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
        };
    }, [isActive, explicitProgress]);

    if (!isActive) return null;

    const currentPhase = RESEARCH_PHASES[currentPhaseIndex];
    const PhaseIcon = currentPhase.icon;

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
    };

    // Estimate remaining (rough)
    const totalEstimated = RESEARCH_PHASES.reduce((sum, p) => sum + p.duration, 0);
    const estimatedRemaining = Math.max(0, totalEstimated - elapsed);

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.95 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="w-full max-w-[85%]"
            >
                <div className="relative rounded-2xl border border-white/10 bg-[#121212] overflow-hidden shadow-2xl shadow-black/50">
                    {/* Glowing top border */}
                    <div className={cn(
                        "absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r",
                        currentPhase.color
                    )} />

                    <div className="p-5 space-y-4">
                        {/* Phase Header */}
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={cn(
                                    "flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br shadow-lg",
                                    currentPhase.color
                                )}>
                                    <PhaseIcon size={18} className="text-white" />
                                </div>
                                <div>
                                    <motion.h3
                                        key={currentPhase.label}
                                        initial={{ opacity: 0, x: -10 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        className="text-sm font-bold text-white tracking-tight"
                                    >
                                        {currentPhase.label}
                                    </motion.h3>
                                    <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest">
                                        Deep Research Mode
                                    </p>
                                </div>
                            </div>
                            <div className="text-right">
                                <span className="text-xs font-mono font-bold text-neutral-400">
                                    {Math.round(progress)}%
                                </span>
                                <p className="text-[10px] text-neutral-600 font-medium">
                                    {typeof explicitProgress === 'number' ? '' : `~${formatTime(estimatedRemaining)} remaining`}
                                </p>
                            </div>
                        </div>

                        {/* Progress Bar */}
                        <div className="relative">
                            <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                                {/* Animated background shimmer */}
                                <div className="absolute inset-0 rounded-full overflow-hidden">
                                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent animate-shimmer" />
                                </div>

                                {/* Progress fill */}
                                <motion.div
                                    className={cn(
                                        "h-full rounded-full bg-gradient-to-r relative",
                                        currentPhase.color
                                    )}
                                    initial={{ width: '0%' }}
                                    animate={{ width: `${progress}%` }}
                                    transition={{ duration: 0.5, ease: 'easeOut' }}
                                >
                                    {/* Glow on progress head */}
                                    <div className="absolute right-0 top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-white/30 blur-sm" />
                                    {/* Pulse dot at the end */}
                                    <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2">
                                        <span className="relative flex h-3 w-3">
                                            <span className={cn(
                                                "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-gradient-to-r",
                                                currentPhase.color
                                            )} />
                                            <span className="relative inline-flex rounded-full h-3 w-3 bg-white shadow-lg" />
                                        </span>
                                    </div>
                                </motion.div>
                            </div>
                        </div>

                        {/* Phase Dots */}
                        <div className="flex items-center justify-between px-1">
                            {RESEARCH_PHASES.map((phase, idx) => {
                                const Icon = phase.icon;
                                const isCompleted = idx < currentPhaseIndex;
                                const isCurrent = idx === currentPhaseIndex;
                                return (
                                    <div
                                        key={idx}
                                        className="flex flex-col items-center gap-1"
                                        title={phase.label}
                                    >
                                        <div className={cn(
                                            "flex h-6 w-6 items-center justify-center rounded-full transition-all duration-500",
                                            isCompleted && "bg-green-500/20 text-green-400",
                                            isCurrent && "bg-white/10 text-white ring-2 ring-white/20",
                                            !isCompleted && !isCurrent && "bg-white/5 text-neutral-600"
                                        )}>
                                            {isCompleted ? (
                                                <CheckCircle2 size={12} />
                                            ) : (
                                                <Icon size={12} className={isCurrent ? "animate-pulse" : ""} />
                                            )}
                                        </div>
                                        <span className={cn(
                                            "text-[8px] font-bold uppercase tracking-wider max-w-[60px] text-center leading-tight hidden sm:block",
                                            isCurrent ? "text-neutral-300" : "text-neutral-600"
                                        )}>
                                            {phase.label.split(' ').slice(0, 2).join(' ')}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Current Status from backend */}
                        {status && status !== 'Thinking...' && (
                            <motion.div
                                key={status}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="flex items-center gap-2 pt-1 border-t border-white/5"
                            >
                                <div className="flex gap-1">
                                    <div className="h-1 w-1 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.3s]" />
                                    <div className="h-1 w-1 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.15s]" />
                                    <div className="h-1 w-1 rounded-full bg-blue-500 animate-bounce" />
                                </div>
                                <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider truncate">
                                    {status}
                                </span>
                            </motion.div>
                        )}
                    </div>
                </div>
            </motion.div>
        </AnimatePresence>
    );
};
