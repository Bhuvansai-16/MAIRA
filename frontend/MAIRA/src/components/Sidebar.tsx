import { MessageSquare, Plus, Settings, History, Menu, Shield, Trash2, LogOut, User } from "lucide-react";
import { cn } from "../lib/utils";
import { useState, memo } from "react";
import { useThreads } from "../hooks/useThreads";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

export const Sidebar = memo(() => {
    const [collapsed, setCollapsed] = useState(false);
    const { user, signOut } = useAuth();
    const navigate = useNavigate();
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
        e.stopPropagation();
        await deleteThread(threadId);
    };

    const handleSignOut = async () => {
        await signOut();
        navigate('/');
    };

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now.getTime() - date.getTime();
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    };

    const cleanTitle = (title: string) => {
        if (!title) return '';
        return title.replace(/\[UPLOADED_FILES:.*?\]/g, '').trim();
    };

    return (
        <div
            className={cn(
                "group/sidebar flex h-screen flex-col border-r border-white/5 bg-[#050505] transition-all duration-500 ease-in-out z-20 relative",
                collapsed ? "w-[72px]" : "w-[280px]"
            )}
        >
            {/* Glossy Overlay */}
            <div className="absolute inset-0 bg-gradient-to-b from-blue-500/5 to-transparent pointer-events-none" />

            <div className="flex items-center justify-between px-5 py-6">
                {!collapsed && (
                    <div className="flex items-center gap-2.5 font-bold text-xl tracking-tight animate-fade-in">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 shadow-lg shadow-blue-500/20">
                            <Shield className="h-5 w-5 text-white" />
                        </div>
                        <span className="text-white">MAIRA</span>
                        <span className="text-[10px] bg-white/10 text-white/50 px-1.5 py-0.5 rounded uppercase tracking-widest font-black">Pro</span>
                    </div>
                )}
                <button
                    onClick={() => setCollapsed(!collapsed)}
                    className={cn(
                        "rounded-xl p-2 text-neutral-500 hover:bg-white/5 hover:text-white transition-all",
                        collapsed && "mx-auto"
                    )}
                    title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                >
                    <Menu size={20} />
                </button>
            </div>

            <div className="px-4 mb-4">
                <button
                    onClick={handleNewChat}
                    className={cn(
                        "group relative flex w-full items-center gap-3 overflow-hidden rounded-xl bg-gradient-to-r from-blue-600 to-blue-500 p-3.5 text-sm font-semibold text-white transition-all hover:scale-[1.02] active:scale-[0.98] shadow-lg shadow-blue-500/10",
                        collapsed && "justify-center px-0"
                    )}
                    title="New conversation"
                >
                    <div className="absolute inset-0 bg-gradient-to-r from-white/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                    <Plus size={18} className="relative z-10" />
                    {!collapsed && <span className="relative z-10 animate-fade-in">New Conversation</span>}
                </button>
            </div>

            <div className="flex-1 overflow-y-auto px-3 scrollbar-hide py-2">
                {!collapsed && (
                    <div className="mb-4 px-3 flex items-center justify-between">
                        <span className="text-[11px] font-bold text-neutral-500 uppercase tracking-[0.1em]">Recent Activity</span>
                    </div>
                )}

                <div className="space-y-1">
                    {isLoadingThreads ? (
                        <div className="flex flex-col gap-2 px-3 py-4">
                            {[1, 2, 3].map(i => (
                                <div key={i} className="h-10 w-full animate-pulse rounded-lg bg-white/5" />
                            ))}
                        </div>
                    ) : threads.length === 0 ? (
                        <div className="px-3 py-8 text-center animate-fade-in">
                            <div className="mx-auto mb-3 h-10 w-10 text-neutral-700">
                                <MessageSquare size={40} strokeWidth={1} />
                            </div>
                            <p className="text-xs text-neutral-500">
                                {!collapsed && "No conversations yet. Start one to begin your research."}
                            </p>
                        </div>
                    ) : (
                        threads.map((thread) => (
                            <button
                                key={thread.thread_id}
                                onClick={() => handleSelectThread(thread.thread_id)}
                                className={cn(
                                    "group relative flex w-full items-center gap-3 rounded-xl p-3 text-sm transition-all duration-200",
                                    collapsed && "justify-center",
                                    currentThreadId === thread.thread_id
                                        ? "bg-white/10 text-white shadow-sm ring-1 ring-white/10"
                                        : "text-neutral-400 hover:bg-white/5 hover:text-white"
                                )}
                            >
                                {currentThreadId === thread.thread_id && (
                                    <div className="absolute left-0 top-1/2 -translate-y-1/2 h-6 w-1 rounded-r-full bg-blue-500" />
                                )}

                                <MessageSquare size={18} className={cn(
                                    "flex-shrink-0 transition-colors",
                                    currentThreadId === thread.thread_id ? "text-blue-400" : "group-hover:text-blue-400"
                                )} />

                                {!collapsed && (
                                    <>
                                        <div className="flex-1 min-w-0 text-left animate-fade-in">
                                            <div className="truncate font-medium">{cleanTitle(thread.title) || 'Untitled Chat'}</div>
                                            <div className="text-[10px] text-neutral-500 mt-0.5 font-medium">
                                                {formatDate(thread.updated_at)}
                                            </div>
                                        </div>
                                        <button
                                            onClick={(e) => handleDeleteThread(e, thread.thread_id)}
                                            className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-500/20 hover:text-red-400 transition-all active:scale-90"
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
            </div>

            <div className="p-3 mt-auto space-y-1 border-t border-white/5 bg-black/40 backdrop-blur-md">
                {/* User Info */}
                {user && (
                    <div className={cn(
                        "flex items-center gap-3 rounded-xl p-3 mb-2",
                        collapsed && "justify-center"
                    )}>
                        {user.user_metadata?.avatar_url ? (
                            <img 
                                src={user.user_metadata.avatar_url} 
                                alt="Avatar"
                                className="h-8 w-8 rounded-lg object-cover"
                            />
                        ) : (
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-600/20 text-violet-400">
                                <User size={16} />
                            </div>
                        )}
                        {!collapsed && (
                            <div className="flex-1 min-w-0 animate-fade-in">
                                <div className="text-xs font-semibold text-white truncate">
                                    {user.user_metadata?.full_name || user.user_metadata?.name || user.email?.split('@')[0]}
                                </div>
                                <div className="text-[10px] text-neutral-500 truncate">
                                    {user.email}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                <button
                    className={cn(
                        "flex w-full items-center gap-3 rounded-xl p-3 text-xs font-semibold text-neutral-400 hover:bg-white/5 hover:text-white transition-all",
                        collapsed && "justify-center"
                    )}
                >
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-neutral-800 text-neutral-400">
                        <History size={16} />
                    </div>
                    {!collapsed && <span className="animate-fade-in">Archive</span>}
                </button>
                <button
                    className={cn(
                        "flex w-full items-center gap-3 rounded-xl p-3 text-xs font-semibold text-neutral-400 hover:bg-white/5 hover:text-white transition-all",
                        collapsed && "justify-center"
                    )}
                >
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-neutral-800 text-neutral-400">
                        <Settings size={16} />
                    </div>
                    {!collapsed && <span className="animate-fade-in">Settings</span>}
                </button>
                
                {/* Sign Out */}
                <button
                    onClick={handleSignOut}
                    className={cn(
                        "flex w-full items-center gap-3 rounded-xl p-3 text-xs font-semibold text-neutral-400 hover:bg-red-500/10 hover:text-red-400 transition-all",
                        collapsed && "justify-center"
                    )}
                    title="Sign out"
                >
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-neutral-800 text-neutral-400 group-hover:bg-red-500/20 group-hover:text-red-400">
                        <LogOut size={16} />
                    </div>
                    {!collapsed && <span className="animate-fade-in">Sign Out</span>}
                </button>
            </div>
        </div>
    );
});

