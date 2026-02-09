import { useState } from 'react';
import { GitBranch, Clock, ChevronRight, History, Loader2, GitFork } from 'lucide-react';
import { cn } from '../lib/utils';
import { useThreads } from '../hooks/useThreads';

interface TimelineViewProps {
    isOpen: boolean;
    onClose: () => void;
}

export const TimelineView = ({ isOpen, onClose }: TimelineViewProps) => {
    const { currentThreadId, checkpoints, fetchStateHistory, branchFromCheckpoint, isLoading } = useThreads();
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);
    const [selectedCheckpoint, setSelectedCheckpoint] = useState<string | null>(null);
    const [isBranching, setIsBranching] = useState(false);

    const loadHistory = async () => {
        if (!currentThreadId) return;
        setIsLoadingHistory(true);
        try {
            await fetchStateHistory(currentThreadId);
        } finally {
            setIsLoadingHistory(false);
        }
    };

    const handleBranch = async (checkpointId: string) => {
        setIsBranching(true);
        setSelectedCheckpoint(checkpointId);
        try {
            const newThread = await branchFromCheckpoint(checkpointId);
            if (newThread) {
                onClose();
            }
        } finally {
            setIsBranching(false);
            setSelectedCheckpoint(null);
        }
    };

    const formatTimestamp = (timestamp: string) => {
        const date = new Date(timestamp);
        return new Intl.DateTimeFormat('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
            month: 'short',
            day: 'numeric'
        }).format(date);
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div 
                className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                onClick={onClose}
            />
            
            {/* Modal */}
            <div className="relative w-full max-w-xl max-h-[80vh] bg-[#121212] border border-white/10 rounded-3xl shadow-2xl overflow-hidden animate-slide-up">
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-600/20 text-purple-400">
                            <History size={20} />
                        </div>
                        <div>
                            <h2 className="text-lg font-black text-white tracking-tight">
                                Conversation Timeline
                            </h2>
                            <p className="text-xs text-neutral-500 font-medium">
                                View history and create branches
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-neutral-500 hover:text-white transition-colors"
                        title="Close timeline"
                        aria-label="Close timeline"
                    >
                        <ChevronRight size={20} className="rotate-90" />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto max-h-[60vh]">
                    {checkpoints.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-12 text-center">
                            <GitBranch size={48} className="text-neutral-600 mb-4" />
                            <h3 className="text-sm font-bold text-neutral-400 mb-2">
                                No Checkpoints Yet
                            </h3>
                            <p className="text-xs text-neutral-500 max-w-xs mb-6">
                                Checkpoints are created as you chat. Load history to see saved states.
                            </p>
                            <button
                                onClick={loadHistory}
                                disabled={isLoadingHistory || !currentThreadId}
                                className={cn(
                                    "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all",
                                    currentThreadId
                                        ? "bg-purple-600 text-white hover:bg-purple-500"
                                        : "bg-neutral-800 text-neutral-500 cursor-not-allowed"
                                )}
                            >
                                {isLoadingHistory ? (
                                    <>
                                        <Loader2 size={16} className="animate-spin" />
                                        Loading...
                                    </>
                                ) : (
                                    <>
                                        <History size={16} />
                                        Load History
                                    </>
                                )}
                            </button>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            <div className="flex items-center justify-between mb-4">
                                <span className="text-xs font-bold text-neutral-500 uppercase tracking-wider">
                                    {checkpoints.length} Checkpoint{checkpoints.length !== 1 ? 's' : ''}
                                </span>
                                <button
                                    onClick={loadHistory}
                                    disabled={isLoadingHistory}
                                    className="flex items-center gap-1.5 text-xs font-bold text-purple-400 hover:text-purple-300 transition-colors"
                                >
                                    {isLoadingHistory ? (
                                        <Loader2 size={12} className="animate-spin" />
                                    ) : (
                                        <History size={12} />
                                    )}
                                    Refresh
                                </button>
                            </div>

                            {/* Timeline */}
                            <div className="relative">
                                {/* Timeline line */}
                                <div className="absolute left-5 top-6 bottom-6 w-px bg-gradient-to-b from-purple-500/50 via-blue-500/30 to-transparent" />

                                {checkpoints.map((checkpoint, index) => (
                                    <div 
                                        key={checkpoint.checkpoint_id}
                                        className={cn(
                                            "relative flex items-start gap-4 p-4 rounded-2xl transition-all",
                                            selectedCheckpoint === checkpoint.checkpoint_id
                                                ? "bg-purple-600/10 border border-purple-500/30"
                                                : "hover:bg-white/5"
                                        )}
                                    >
                                        {/* Timeline dot */}
                                        <div className={cn(
                                            "relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-all",
                                            index === 0 
                                                ? "bg-purple-600/30 text-purple-400 ring-2 ring-purple-500/20"
                                                : "bg-white/5 text-neutral-500"
                                        )}>
                                            <Clock size={16} />
                                        </div>

                                        {/* Content */}
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className={cn(
                                                    "text-sm font-bold",
                                                    index === 0 ? "text-white" : "text-neutral-300"
                                                )}>
                                                    {index === 0 ? "Current State" : `Checkpoint ${checkpoints.length - index}`}
                                                </span>
                                                {checkpoint.parent_checkpoint_id && (
                                                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 text-[10px] font-bold uppercase">
                                                        <GitFork size={10} />
                                                        Branch
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-xs text-neutral-500 font-medium mb-3">
                                                {formatTimestamp(checkpoint.timestamp)}
                                            </p>
                                            
                                            {/* Message preview */}
                                            {checkpoint.message_count && (
                                                <p className="text-xs text-neutral-600 mb-3">
                                                    {checkpoint.message_count} messages in conversation
                                                </p>
                                            )}

                                            {/* Actions */}
                                            {index !== 0 && (
                                                <button
                                                    onClick={() => handleBranch(checkpoint.checkpoint_id)}
                                                    disabled={isBranching || isLoading}
                                                    className={cn(
                                                        "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all",
                                                        isBranching && selectedCheckpoint === checkpoint.checkpoint_id
                                                            ? "bg-purple-600/20 text-purple-400"
                                                            : "bg-white/5 text-neutral-400 hover:bg-purple-600/20 hover:text-purple-400"
                                                    )}
                                                >
                                                    {isBranching && selectedCheckpoint === checkpoint.checkpoint_id ? (
                                                        <>
                                                            <Loader2 size={12} className="animate-spin" />
                                                            Creating Branch...
                                                        </>
                                                    ) : (
                                                        <>
                                                            <GitBranch size={12} />
                                                            Branch from here
                                                        </>
                                                    )}
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-white/5 bg-black/20">
                    <p className="text-[10px] text-neutral-600 text-center font-medium">
                        💡 Tip: Edit any message to automatically create a branch
                    </p>
                </div>
            </div>
        </div>
    );
};
