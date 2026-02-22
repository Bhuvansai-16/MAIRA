import { useState, useEffect } from 'react';
import { Sparkles, Search, FileText, CheckCircle2, Brain, ClipboardList } from 'lucide-react';
import { cn } from '../lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import type { ResearchPhase } from '../types/agent';

interface DeepResearchProgressProps {
    status?: string;
    statusDetail?: string;  // Additional detail from backend
    statusIcon?: string;    // Icon from backend
    isActive: boolean;
    progress?: number;
    currentPhase?: ResearchPhase;  // Phase directly from backend
    phaseName?: string;     // Phase display name from backend
    phaseDescription?: string;  // Phase description from backend
}

// Research phases aligned with backend RESEARCH_PHASES
// We use these as the "High Level Plan" for now since we don't receive a dynamic plan from the backend yet.
const RESEARCH_PHASES = [
    { key: 'planning', label: 'Planning Strategy', icon: ClipboardList },
    { key: 'searching', label: 'Gathering Information', icon: Search },
    { key: 'drafting', label: 'Drafting Content', icon: FileText },
    { key: 'reasoning', label: 'Deep Reasoning', icon: Brain },
    { key: 'finalizing', label: 'Finalizing Report', icon: CheckCircle2 },
];

// Map phase key to index
const PHASE_INDEX_MAP: Record<string, number> = {
    reasoning: 3,
    finalizing: 4,
    completed: 5,
    // Aliases
    plan: 0,
    search: 1,
    draft: 2,
    reason: 3,
    finalize: 4,
    done: 5
};

export const DeepResearchProgress = ({
    status,
    statusDetail,
    isActive,
    progress: explicitProgress,
    currentPhase,
    phaseDescription
}: DeepResearchProgressProps) => {
    const [progress, setProgress] = useState(0);
    const [currentPhaseIndex, setCurrentPhaseIndex] = useState(0);
    const [displayStatus, setDisplayStatus] = useState<string>('');
    const [expanded, setExpanded] = useState(true);

    // Determine phase from backend phase event (preferred) or fallback to status text
    useEffect(() => {
        if (!isActive) {
            setCurrentPhaseIndex(0);
            return;
        }

        let newIndex: number | undefined;

        // PRIMARY: Use phase directly from backend if available
        if (currentPhase) {
            const normalizedPhase = currentPhase.toLowerCase();
            let foundIndex = PHASE_INDEX_MAP[normalizedPhase];

            if (foundIndex === undefined) {
                const key = Object.keys(PHASE_INDEX_MAP).find(k => normalizedPhase.includes(k));
                if (key) foundIndex = PHASE_INDEX_MAP[key];
            }

            if (foundIndex !== undefined) {
                newIndex = foundIndex;
            }
        }

        // FALLBACK: Aggressively parse ALL text (status + details) for keywords
        if (newIndex === undefined) {
            const combinedText = `${status || ''} ${statusDetail || ''} ${currentPhase || ''}`.toLowerCase();

            if (combinedText.includes('plan') || combinedText.includes('todo')) {
                newIndex = 0;
            } else if (combinedText.includes('search') || combinedText.includes('web') || combinedText.includes('arxiv') || combinedText.includes('paper') || combinedText.includes('github') || combinedText.includes('gather')) {
                newIndex = 1;
            } else if (combinedText.includes('draft') || combinedText.includes('writ') || combinedText.includes('generat') || combinedText.includes('analyz') || combinedText.includes('extract') || combinedText.includes('read')) {
                // We map 'analyzing' and 'extracting' keywords to Drafting phase now that Analyzing is removed
                newIndex = 2;
            } else if (combinedText.includes('reason') || combinedText.includes('verify') || combinedText.includes('think') || combinedText.includes('check')) {
                newIndex = 3;
            } else if (combinedText.includes('final') || combinedText.includes('complet') || combinedText.includes('report') || combinedText.includes('summar') || combinedText.includes('export') || combinedText.includes('pdf')) {
                newIndex = 4;
            }
        }

        // TERTIARY: Update phase based on explicit progress percentage
        if (newIndex === undefined && typeof explicitProgress === 'number') {
            if (explicitProgress >= 90) newIndex = 4;
            else if (explicitProgress >= 70) newIndex = 3;
            else if (explicitProgress >= 40) newIndex = 2;
            else if (explicitProgress >= 15) newIndex = 1;
            else newIndex = 0;
        }

        // LATCH: Only allow phase to move FORWARD, never backwards
        if (newIndex !== undefined) {
            setCurrentPhaseIndex(prev => Math.max(prev, newIndex!));
        }
    }, [status, statusDetail, isActive, explicitProgress, currentPhase]);

    useEffect(() => {
        if (status) setDisplayStatus(status);
    }, [status, statusDetail]);

    // Handle progress updates with anti-regression latch
    useEffect(() => {
        if (!isActive) {
            setProgress(0);
            return;
        }

        if (typeof explicitProgress === 'number') {
            // LATCH: Only move forward
            setProgress(prev => Math.max(prev, explicitProgress));
        }
    }, [isActive, explicitProgress]);

    if (!isActive) return null;

    return (
        <AnimatePresence>
            <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="w-full max-w-md font-sans"
            >
                <div className="bg-[#121212] border border-white/10 rounded-xl overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-300">

                    {/* Header */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 bg-white/[0.02]">
                        <div className="flex items-center gap-2">
                            <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400">
                                <Sparkles size={14} />
                            </div>
                            <h3 className="text-sm font-semibold text-neutral-200">
                                {phaseDescription || 'Deep Research'}
                            </h3>
                        </div>
                        <button
                            onClick={() => setExpanded(!expanded)}
                            className="text-neutral-500 hover:text-white transition-colors"
                        >
                            {/* Simple toggle if needed, or just status badge */}
                            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-white/5 border border-white/5">
                                {expanded ? 'Hide' : 'Show'}
                            </span>
                        </button>
                    </div>

                    {/* Content */}
                    <AnimatePresence initial={false}>
                        {expanded && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                                className="border-b border-white/5"
                            >
                                <div className="p-4 space-y-3">
                                    {RESEARCH_PHASES.map((phase, idx) => {
                                        const isCompleted = idx < currentPhaseIndex;
                                        const isCurrent = idx === currentPhaseIndex;

                                        return (
                                            <div key={phase.key} className="flex items-start gap-3">
                                                <div className="relative flex items-center justify-center pt-0.5">
                                                    {isCompleted ? (
                                                        <div className="h-4 w-4 rounded-full bg-neutral-800 border border-neutral-700 flex items-center justify-center text-neutral-400">
                                                            <CheckCircle2 size={10} />
                                                        </div>
                                                    ) : isCurrent ? (
                                                        <div className="relative h-4 w-4">
                                                            <div className="absolute inset-0 rounded-full border-2 border-white/20" />
                                                            <div className="absolute inset-0 rounded-full border-2 border-t-blue-500 animate-spin" />
                                                        </div>
                                                    ) : (
                                                        <div className="h-4 w-4 rounded-full border border-dashed border-neutral-700 bg-transparent" />
                                                    )}

                                                    {/* Connector Line */}
                                                    {idx !== RESEARCH_PHASES.length - 1 && (
                                                        <div className={cn(
                                                            "absolute top-5 left-1/2 -translate-x-1/2 w-[1px] h-3 bg-neutral-800",
                                                            (isCompleted) && "bg-neutral-700"
                                                        )} />
                                                    )}
                                                </div>

                                                <span className={cn(
                                                    "text-sm font-medium transition-colors duration-300",
                                                    isCurrent ? "text-blue-100" : isCompleted ? "text-neutral-300" : "text-neutral-500"
                                                )}>
                                                    {phase.label}

                                                    {/* NEW: Show the actual subagent name next to the active phase */}
                                                    {isCurrent && status && (
                                                        <span className="ml-2 text-[10px] text-blue-300/80 font-mono tracking-wider animate-pulse">
                                                            [{status}]
                                                        </span>
                                                    )}
                                                </span>
                                            </div>
                                        );
                                    })}
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Footer / Current Action Log */}
                    <div className="p-3 bg-black/20 flex flex-col gap-2">
                        <div className="flex items-center gap-2.5">
                            {/* Spinner for active state */}
                            <div className="relative flex h-3 w-3">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-500 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
                            </div>

                            <span className="text-xs font-medium text-blue-400/90 tracking-wide">
                                Researching...
                            </span>
                        </div>

                        {/* Actual log message from backend (statusDetail) */}
                        {(statusDetail || displayStatus) && (
                            <div className="pl-5.5">
                                <p className="text-[11px] text-neutral-400 font-mono leading-relaxed truncate opacity-80">
                                    {statusDetail || displayStatus}
                                </p>
                            </div>
                        )}

                        {/* Bottom Thin Progress Bar */}
                        <div className="mt-2 h-1 w-full bg-white/5 rounded-full overflow-hidden">
                            <motion.div
                                className="h-full bg-blue-500 rounded-full"
                                initial={{ width: "0%" }}
                                animate={{ width: `${progress}%` }}
                                transition={{ duration: 0.3 }}
                            />
                        </div>
                    </div>
                </div>
            </motion.div>
        </AnimatePresence>
    );
};
