import { useState } from 'react';
import { 
    Shield, 
    CheckCircle2, 
    FileCheck, 
    BookOpen, 
    ChevronDown, 
    ChevronUp,
    AlertCircle
} from 'lucide-react';
import { cn } from '../lib/utils';
import { VerificationBadge, type VerificationStatus } from './VerificationBadge';

export interface VerificationDetails {
    overallScore: number;
    status: VerificationStatus;
    citationScore?: number;
    factCheckScore?: number;
    qualityScore?: number;
    completenessScore?: number;
    validCitations?: number;
    totalCitations?: number;
    verifiedFacts?: number;
    totalFacts?: number;
    issues?: string[];
    timestamp?: string;
}

interface VerificationScoreProps {
    verification: VerificationDetails;
    className?: string;
    compact?: boolean;
}

const getScoreColor = (score: number) => {
    if (score >= 85) return 'text-emerald-400';
    if (score >= 60) return 'text-amber-400';
    return 'text-red-400';
};

const getProgressColor = (score: number) => {
    if (score >= 85) return 'stroke-emerald-500';
    if (score >= 60) return 'stroke-amber-500';
    return 'stroke-red-500';
};

const getProgressBg = (score: number) => {
    if (score >= 85) return 'stroke-emerald-500/20';
    if (score >= 60) return 'stroke-amber-500/20';
    return 'stroke-red-500/20';
};

// Circular progress indicator component outside to avoid re-creation on render
const CircularProgress = ({ score, size = 48 }: { score: number; size?: number }) => {
    const radius = (size - 8) / 2;
    const circumference = 2 * Math.PI * radius;
    const progress = ((100 - score) / 100) * circumference;

    return (
        <div 
            className={cn(
                "relative flex items-center justify-center shrink-0",
                size === 32 ? "w-8 h-8" : "w-12 h-12"
            )}
        >
            <svg 
                className="transform -rotate-90" 
                width={size} 
                height={size}
            >
                {/* Background circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    strokeWidth="4"
                    className={getProgressBg(score)}
                />
                {/* Progress circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    strokeWidth="4"
                    strokeLinecap="round"
                    className={cn(getProgressColor(score), "transition-all duration-1000 ease-out")}
                    strokeDasharray={circumference}
                    strokeDashoffset={progress}
                />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
                <span className={cn("font-black tabular-nums", size === 32 ? "text-[10px]" : "text-sm", getScoreColor(score))}>
                    {score}
                </span>
            </div>
        </div>
    );
};

export const VerificationScore = ({ 
    verification, 
    className,
    compact = false 
}: VerificationScoreProps) => {
    const [isExpanded, setIsExpanded] = useState(false);

    // Compact view
    if (compact) {
        return (
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className={cn(
                    "flex items-center gap-2 text-left transition-all",
                    className
                )}
                title={isExpanded ? "Collapse verification details" : "Expand verification details"}
            >
                <CircularProgress score={verification.overallScore} size={32} />
                <VerificationBadge status={verification.status} showLabel={false} />
            </button>
        );
    }

    return (
        <div className={cn(
            "rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm overflow-hidden transition-all duration-300",
            isExpanded ? "shadow-xl shadow-black/20" : "",
            className
        )}>
            {/* Header */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-white/5 transition-colors"
                title={isExpanded ? "Collapse verification details" : "Expand verification details"}
            >
                <div className="flex items-center gap-3">
                    <CircularProgress score={verification.overallScore} />
                    <div className="text-left">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-neutral-500 mb-0.5">
                            Verification Score
                        </div>
                        <VerificationBadge status={verification.status} />
                    </div>
                </div>
                <div className="flex items-center gap-2 text-neutral-500">
                    <span className="text-[10px] font-bold uppercase tracking-wider">
                        {isExpanded ? 'Hide' : 'Details'}
                    </span>
                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </div>
            </button>

            {/* Expanded Details */}
            {isExpanded && (
                <div className="px-4 pb-4 pt-2 border-t border-white/5 animate-slide-down">
                    {/* Score Breakdown */}
                    <div className="grid grid-cols-2 gap-3 mb-4">
                        {verification.citationScore !== undefined && (
                            <ScoreItem 
                                icon={FileCheck}
                                label="Citations"
                                score={verification.citationScore}
                                detail={verification.validCitations !== undefined && verification.totalCitations !== undefined
                                    ? `${verification.validCitations}/${verification.totalCitations} valid`
                                    : undefined
                                }
                            />
                        )}
                        {verification.factCheckScore !== undefined && (
                            <ScoreItem 
                                icon={CheckCircle2}
                                label="Fact Check"
                                score={verification.factCheckScore}
                                detail={verification.verifiedFacts !== undefined && verification.totalFacts !== undefined
                                    ? `${verification.verifiedFacts}/${verification.totalFacts} verified`
                                    : undefined
                                }
                            />
                        )}
                        {verification.qualityScore !== undefined && (
                            <ScoreItem 
                                icon={Shield}
                                label="Quality"
                                score={verification.qualityScore}
                            />
                        )}
                        {verification.completenessScore !== undefined && (
                            <ScoreItem 
                                icon={BookOpen}
                                label="Completeness"
                                score={verification.completenessScore}
                            />
                        )}
                    </div>

                    {/* Issues */}
                    {verification.issues && verification.issues.length > 0 && (
                        <div className="pt-3 border-t border-white/5">
                            <div className="flex items-center gap-2 text-amber-400 mb-2">
                                <AlertCircle size={14} />
                                <span className="text-[10px] font-bold uppercase tracking-wider">
                                    Issues Found ({verification.issues.length})
                                </span>
                            </div>
                            <ul className="space-y-1.5">
                                {verification.issues.slice(0, 3).map((issue, idx) => (
                                    <li key={idx} className="flex items-start gap-2 text-xs text-neutral-400">
                                        <span className="text-amber-500 mt-0.5">•</span>
                                        <span>{issue}</span>
                                    </li>
                                ))}
                                {verification.issues.length > 3 && (
                                    <li className="text-xs text-neutral-500 italic pl-4">
                                        +{verification.issues.length - 3} more issues
                                    </li>
                                )}
                            </ul>
                        </div>
                    )}

                    {/* Timestamp */}
                    {verification.timestamp && (
                        <div className="mt-3 pt-3 border-t border-white/5 text-[10px] text-neutral-600 text-right">
                            Verified at {new Date(verification.timestamp).toLocaleTimeString()}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

// Score item component
interface ScoreItemProps {
    icon: React.ComponentType<{ size?: number; className?: string }>;
    label: string;
    score: number;
    detail?: string;
}

const ScoreItem = ({ icon: Icon, label, score, detail }: ScoreItemProps) => {
    const getColor = (score: number) => {
        if (score >= 85) return 'text-emerald-400';
        if (score >= 60) return 'text-amber-400';
        return 'text-red-400';
    };

    const getBgColor = (score: number) => {
        if (score >= 85) return 'bg-emerald-500/10';
        if (score >= 60) return 'bg-amber-500/10';
        return 'bg-red-500/10';
    };

    return (
        <div className={cn(
            "rounded-xl p-3 transition-colors",
            getBgColor(score)
        )}>
            <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                    <Icon size={12} className={getColor(score)} />
                    <span className="text-[10px] font-bold uppercase tracking-wider text-neutral-400">
                        {label}
                    </span>
                </div>
                <span className={cn("text-sm font-black tabular-nums", getColor(score))}>
                    {score}%
                </span>
            </div>
            {detail && (
                <div className="text-[10px] text-neutral-500 mt-1">
                    {detail}
                </div>
            )}
        </div>
    );
};

export default VerificationScore;
