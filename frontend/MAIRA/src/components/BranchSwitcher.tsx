import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '../lib/utils';

interface BranchSwitcherProps {
    currentVersion: number;
    totalVersions: number;
    onVersionChange?: (version: number) => void;
    onPrevious?: () => void;
    onNext?: () => void;
    onEdit?: () => void;
    className?: string;
}

export const BranchSwitcher = ({
    currentVersion,
    totalVersions,
    onVersionChange,
    onPrevious,
    onNext,
    onEdit,
    className
}: BranchSwitcherProps) => {
    if (totalVersions <= 1 && !onEdit) return null;

    const handlePrev = () => {
        if (onPrevious) onPrevious();
        else if (onVersionChange) onVersionChange(Math.max(0, currentVersion - 1));
    };

    const handleNext = () => {
        if (onNext) onNext();
        else if (onVersionChange) onVersionChange(Math.min(totalVersions - 1, currentVersion + 1));
    };

    return (
        <div className={cn("flex items-center gap-1 text-neutral-400 select-none", className)}>
            {totalVersions > 1 && (
                <div className="flex items-center bg-white/5 rounded-lg border border-white/5 overflow-hidden">
                    <button
                        onClick={handlePrev}
                        disabled={currentVersion === 0}
                        className="p-1 hover:bg-white/10 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                        title="Previous version"
                    >
                        <ChevronLeft size={12} />
                    </button>
                    <span className="text-[10px] font-medium px-1.5 min-w-[24px] text-center">
                        {currentVersion + 1} / {totalVersions}
                    </span>
                    <button
                        onClick={handleNext}
                        disabled={currentVersion === totalVersions - 1}
                        className="p-1 hover:bg-white/10 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
                        title="Next version"
                    >
                        <ChevronRight size={12} />
                    </button>
                </div>
            )}
        </div>
    );
};
