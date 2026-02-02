import { useState, useRef, useEffect } from "react";
import { Send, Mic, MicOff, Paperclip, Sparkles, Shield, GitBranch } from "lucide-react";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { MessageBubble } from "./MessageBubble";
import { TimelineView } from "./TimelineView";
import { cn } from "../lib/utils";
import { useThreads } from "../context/ThreadContext";

export const ChatArea = () => {
    const { currentMessages, isLoading, sendMessage, currentThreadId, deepResearch, setDeepResearch, editMessage } = useThreads();
    const [input, setInput] = useState("");
    const [isTimelineOpen, setIsTimelineOpen] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const { isListening, error: speechError, startListening, stopListening, hasRecognition } = useSpeechRecognition((text) => {
        setInput(prev => prev + (prev ? ' ' : '') + text);
    });

    // Show speech error if any
    useEffect(() => {
        if (speechError) {
            alert(speechError); // Simple alert for now, could be a toast
        }
    }, [speechError]);

    // Scroll to bottom
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [currentMessages]);

    const handleSend = async () => {
        if (!input.trim() || isLoading) return;

        const userMessage = input;
        setInput(""); // Clear input early
        await sendMessage(userMessage);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    // Toggle timeline view
    const toggleTimeline = () => setIsTimelineOpen(prev => !prev);

    return (
        <div className="flex h-screen flex-1 flex-col bg-[#080808] relative overflow-hidden">
            {/* Background Gradient */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-4xl h-[500px] bg-blue-600/5 blur-[120px] pointer-events-none" />

            {/* Header */}
            <header className="flex h-[72px] items-center justify-between border-b border-white/5 bg-black/20 backdrop-blur-2xl px-8 sticky top-0 z-20">
                <div className="flex items-center gap-4">
                    <div className="flex flex-col">
                        <h1 className="text-sm font-bold text-white tracking-tight">
                            {currentThreadId ? "Research Session" : "New Research"}
                        </h1>
                        <div className="flex items-center gap-2">
                            <div className="relative flex h-1.5 w-1.5">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500"></span>
                            </div>
                            <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-widest">
                                Online & Ready
                            </span>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {currentThreadId && (
                        <button
                            onClick={toggleTimeline}
                            className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-neutral-400 hover:text-white hover:bg-white/10 transition-all"
                            title="View conversation timeline"
                        >
                            <GitBranch size={14} />
                            <span className="text-[10px] font-bold uppercase tracking-wider hidden sm:inline">Timeline</span>
                        </button>
                    )}
                    <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
                        <div className="h-1 w-1 rounded-full bg-blue-400" />
                        <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">Mistral Large 2</span>
                    </div>
                </div>
            </header>

            {/* Messages Area */}
            <main className="flex-1 overflow-y-auto overflow-x-hidden scroll-smooth">
                <div className="mx-auto max-w-4xl w-full px-6 py-12">
                    {currentMessages.length === 0 ? (
                        <div className="flex h-[60vh] flex-col items-center justify-center text-center animate-fade-in">
                            <div className="mb-8 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-blue-600 to-blue-500 shadow-2xl shadow-blue-500/20">
                                <Shield className="h-10 w-10 text-white" />
                            </div>
                            <h2 className="mb-3 text-3xl font-black text-white tracking-tight">
                                How can I assist your <span className="text-gradient">research</span> today?
                            </h2>
                            <p className="max-w-md text-sm text-neutral-400 leading-relaxed font-medium">
                                MAIRA is your advanced agentic research assistant. I can browse the web, analyze papers, and generate comprehensive reports.
                            </p>

                            <div className="mt-12 grid grid-cols-1 md:grid-cols-2 gap-3 w-full max-w-lg">
                                {[
                                    "Research the future of AI agents",
                                    "Analyze recent CRISPR breakthroughs",
                                    "Compare EV battery technologies",
                                    "Summarize GPU architecture trends"
                                ].map((suggestion) => (
                                    <button
                                        key={suggestion}
                                        onClick={() => setInput(suggestion)}
                                        className="p-4 text-left text-xs font-semibold text-neutral-400 bg-white/5 border border-white/5 rounded-2xl hover:bg-white/10 hover:border-white/10 hover:text-white transition-all group"
                                        title={`Ask about: ${suggestion}`}
                                    >
                                        <span className="flex items-center justify-between">
                                            {suggestion}
                                            <Send size={12} className="opacity-0 group-hover:opacity-100 -translate-x-2 group-hover:translate-x-0 transition-all" />
                                        </span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col gap-8">
                            {currentMessages.map((msg, index) => (
                                <div 
                                    key={msg.message_id || index} 
                                    className="animate-slide-up"
                                >
                                    <MessageBubble
                                        role={msg.role}
                                        content={msg.content}
                                        thought={msg.thought}
                                        status={msg.status}
                                        download={msg.download}
                                        verification={msg.verification}
                                        reasoning={msg.reasoning}
                                        messageIndex={index}
                                        onEdit={editMessage}
                                        isStreaming={msg.type === 'streaming'}
                                    />
                                </div>
                            ))}

                            {isLoading && currentMessages[currentMessages.length - 1]?.role === 'user' && (
                                <div className="animate-slide-up">
                                    <MessageBubble
                                        role="agent"
                                        content=""
                                        status="Thinking..."
                                        isStreaming={true}
                                    />
                                </div>
                            )}
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </main>

            {/* Input Area */}
            <footer className="p-6 md:p-10 relative z-20">
                <div className="mx-auto max-w-3xl">
                    <div className="relative group/input">
                        {/* Glow effect on focus */}
                        <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-purple-600 rounded-[28px] opacity-0 group-focus-within/input:opacity-10 transition-opacity blur-md" />

                        <div className="relative flex items-end gap-3 rounded-[24px] border border-white/10 bg-[#121212]/80 backdrop-blur-3xl p-4 shadow-[0_20px_50px_rgba(0,0,0,0.5)] focus-within:border-white/20 transition-all duration-300">
                            <button className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl text-neutral-500 hover:bg-white/5 hover:text-white transition-all active:scale-90" title="Attach file">
                                <Paperclip size={20} />
                            </button>

                            <textarea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Message MAIRA..."
                                className="max-h-[250px] min-h-[44px] w-full resize-none bg-transparent py-3 text-sm text-white placeholder-neutral-500 focus:outline-none font-medium leading-relaxed"
                                rows={1}
                                aria-label="Message input"
                            />

                            <div className="flex items-center gap-2 pb-1 pr-1">
                                {hasRecognition && (
                                    <button
                                        onClick={isListening ? stopListening : startListening}
                                        className={cn(
                                            "flex h-9 w-9 items-center justify-center rounded-xl transition-all duration-300",
                                            isListening
                                                ? "bg-red-500/10 text-red-500 animate-pulse ring-1 ring-red-500/20"
                                                : "text-neutral-500 hover:bg-white/5 hover:text-white"
                                        )}
                                        title={isListening ? "Stop listening" : "Voice input"}
                                    >
                                        {isListening ? <MicOff size={18} /> : <Mic size={18} />}
                                    </button>
                                )}

                                <button
                                    onClick={() => setDeepResearch(!deepResearch)}
                                    className={cn(
                                        "flex h-9 items-center gap-2 px-3.5 rounded-xl transition-all duration-300 font-bold text-[10px] uppercase tracking-wider",
                                        deepResearch
                                            ? "bg-gradient-to-r from-purple-600 to-blue-600 text-white shadow-lg shadow-purple-500/20 hover:scale-105 active:scale-95"
                                            : "bg-white/5 text-neutral-500 hover:bg-white/10 hover:text-white"
                                    )}
                                    title={deepResearch ? "Deep research enabled" : "Enable deep research"}
                                >
                                    <Sparkles size={14} className={cn(deepResearch && "animate-pulse")} />
                                    <span className="hidden sm:inline">Deep Research</span>
                                </button>

                                <button
                                    onClick={handleSend}
                                    disabled={!input.trim() || isLoading}
                                    className={cn(
                                        "flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl transition-all duration-300",
                                        input.trim() && !isLoading
                                            ? "bg-white text-black hover:scale-105 active:scale-95 shadow-lg shadow-white/5"
                                            : "bg-white/5 text-neutral-600 cursor-not-allowed"
                                    )}
                                    title="Send message"
                                >
                                    <Send size={18} />
                                </button>
                            </div>
                        </div>
                    </div>
                    <p className="mt-4 text-center text-[10px] font-bold text-neutral-600 uppercase tracking-[0.2em] animate-fade-in">
                        AI-Augmented Research Agent • v1.0.4
                    </p>
                </div>
            </footer>

            {/* Timeline Modal */}
            <TimelineView 
                isOpen={isTimelineOpen} 
                onClose={() => setIsTimelineOpen(false)} 
            />
        </div>
    );
};

