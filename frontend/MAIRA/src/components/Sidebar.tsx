import { MessageSquare, Plus, Settings, History, Menu, Shield, Trash2, Loader2 } from "lucide-react";
import { cn } from "../lib/utils";
import { useState } from "react";
import { useThreads } from "../context/ThreadContext";

export const Sidebar = () => {
    const [collapsed, setCollapsed] = useState(false);
    const {
        threads,
        currentThreadId,
        isLoadingThreads,
        selectThread,
        deleteThread,
        startNewChat
    } = useThreads();

    const handleNewChat = () => {
        startNewChat();
    };

    const handleSelectThread = async (threadId: string) => {
        await selectThread(threadId);
    };

    const handleDeleteThread = async (e: React.MouseEvent, threadId: string) => {
        e.stopPropagation(); // Prevent selecting the thread
        await deleteThread(threadId);
    };

    // Format date for display
    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays} days ago`;
        return date.toLocaleDateString();
    };

    return (
        <div
            className={cn(
                "flex h-screen flex-col border-r border-neutral-800 bg-black transition-all duration-300",
                collapsed ? "w-16" : "w-64"
            )}
        >
            <div className="flex items-center justify-between p-4">
                {!collapsed && (
                    <div className="flex items-center gap-2 font-bold text-xl text-white">
                        <Shield className="h-6 w-6 text-blue-500" />
                        <span>MAIRA</span>
                    </div>
                )}
                <button
                    onClick={() => setCollapsed(!collapsed)}
                    className="rounded-lg p-2 text-neutral-400 hover:bg-neutral-800 hover:text-white"
                >
                    <Menu size={20} />
                </button>
            </div>

            <div className="p-2">
                <button
                    onClick={handleNewChat}
                    className={cn(
                        "flex w-full items-center gap-2 rounded-lg bg-blue-600 p-3 text-sm font-medium text-white transition-colors hover:bg-blue-700",
                        collapsed && "justify-center px-0"
                    )}
                >
                    <Plus size={20} />
                    {!collapsed && <span>New Chat</span>}
                </button>
            </div>

            <div className="flex-1 overflow-y-auto px-2 py-4">
                <div className="mb-2 px-2 text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                    {!collapsed && "Recent Conversations"}
                </div>

                {isLoadingThreads ? (
                    <div className="flex items-center justify-center py-4">
                        <Loader2 className="h-5 w-5 animate-spin text-neutral-500" />
                    </div>
                ) : threads.length === 0 ? (
                    <div className="px-2 py-4 text-center text-sm text-neutral-500">
                        {!collapsed && "No conversations yet"}
                    </div>
                ) : (
                    threads.map((thread) => (
                        <button
                            key={thread.thread_id}
                            onClick={() => handleSelectThread(thread.thread_id)}
                            className={cn(
                                "group flex w-full items-center gap-3 rounded-lg p-3 text-sm transition-all",
                                collapsed && "justify-center",
                                currentThreadId === thread.thread_id
                                    ? "bg-neutral-800 text-white"
                                    : "text-neutral-400 hover:bg-neutral-900 hover:text-white"
                            )}
                        >
                            <MessageSquare size={18} className="flex-shrink-0" />
                            {!collapsed && (
                                <>
                                    <div className="flex-1 min-w-0 text-left">
                                        <div className="truncate">{thread.title}</div>
                                        <div className="text-xs text-neutral-500 mt-0.5">
                                            {formatDate(thread.updated_at)}
                                        </div>
                                    </div>
                                    <button
                                        onClick={(e) => handleDeleteThread(e, thread.thread_id)}
                                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/20 hover:text-red-400 transition-all"
                                        title="Delete conversation"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </>
                            )}
                        </button>
                    ))
                )}
            </div>

            <div className="border-t border-neutral-800 p-2">
                <button
                    className={cn(
                        "flex w-full items-center gap-3 rounded-lg p-3 text-sm text-neutral-400 hover:bg-neutral-900 hover:text-white transition-all",
                        collapsed && "justify-center"
                    )}
                >
                    <History size={18} />
                    {!collapsed && <span>History</span>}
                </button>
                <button
                    className={cn(
                        "flex w-full items-center gap-3 rounded-lg p-3 text-sm text-neutral-400 hover:bg-neutral-900 hover:text-white transition-all",
                        collapsed && "justify-center"
                    )}
                >
                    <Settings size={18} />
                    {!collapsed && <span>Settings</span>}
                </button>
            </div>
        </div>
    );
};

