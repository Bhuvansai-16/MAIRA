import { useState, useRef, useEffect } from "react";
import { Send, Mic, MicOff, Paperclip } from "lucide-react";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { MessageBubble } from "./MessageBubble";
import { cn } from "../lib/utils";
import { useThreads } from "../context/ThreadContext";

export const ChatArea = () => {
    const { currentMessages, isLoading, sendMessage, currentThreadId } = useThreads();
    const [input, setInput] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const { isListening, transcript, startListening, stopListening, hasRecognition } = useSpeechRecognition();

    // Scroll to bottom
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [currentMessages]);

    // Update input with speech transcript
    useEffect(() => {
        if (transcript) {
            setInput((prev) => prev + (prev ? " " : "") + transcript);
        }
    }, [transcript]);

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

    return (
        <div className="flex h-screen flex-1 flex-col bg-black">
            {/* Header - show current thread info */}
            <div className="border-b border-neutral-800 px-6 py-3">
                <div className="text-sm text-neutral-400">
                    {currentThreadId ? (
                        <span className="flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full bg-green-500"></span>
                            Active conversation
                        </span>
                    ) : (
                        <span className="flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full bg-blue-500"></span>
                            New conversation
                        </span>
                    )}
                </div>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 md:p-8">
                <div className="mx-auto flex max-w-3xl flex-col gap-6">
                    {currentMessages.map((msg, index) => (
                        <MessageBubble key={index} role={msg.role} content={msg.content} />
                    ))}
                    {isLoading && (
                        <div className="flex items-center gap-2 p-4 text-neutral-400">
                            <div className="h-2 w-2 animate-bounce rounded-full bg-blue-500"></div>
                            <div className="h-2 w-2 animate-bounce rounded-full bg-blue-500 delay-75"></div>
                            <div className="h-2 w-2 animate-bounce rounded-full bg-blue-500 delay-150"></div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Input Area */}
            <div className="p-4 md:p-6">
                <div className="mx-auto max-w-3xl">
                    <div className="relative flex items-end gap-2 rounded-2xl border border-neutral-800 bg-neutral-900 p-2 shadow-lg focus-within:border-neutral-700 focus-within:ring-1 focus-within:ring-blue-500/50">
                        <button className="flex h-10 w-10 items-center justify-center rounded-full text-neutral-400 hover:bg-neutral-800 hover:text-white transition-colors">
                            <Paperclip size={20} />
                        </button>

                        <textarea
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Ask anything..."
                            className="max-h-[200px] min-h-[44px] w-full resize-none bg-transparent py-3 text-sm text-white placeholder-neutral-500 focus:outline-none"
                            rows={1}
                        />

                        {hasRecognition && (
                            <button
                                onClick={isListening ? stopListening : startListening}
                                className={cn(
                                    "flex h-10 w-10 items-center justify-center rounded-full transition-colors",
                                    isListening
                                        ? "bg-red-500/20 text-red-500 animate-pulse"
                                        : "text-neutral-400 hover:bg-neutral-800 hover:text-white"
                                )}
                                title="Voice input"
                            >
                                {isListening ? <MicOff size={20} /> : <Mic size={20} />}
                            </button>
                        )}

                        <button
                            onClick={handleSend}
                            disabled={!input.trim() || isLoading}
                            className={cn(
                                "flex h-10 w-10 items-center justify-center rounded-full transition-all",
                                input.trim() && !isLoading
                                    ? "bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-500/20"
                                    : "bg-neutral-800 text-neutral-500 cursor-not-allowed"
                            )}
                        >
                            <Send size={18} />
                        </button>
                    </div>
                    <div className="mt-2 text-center text-xs text-neutral-600">
                        MAIRA can make mistakes. Consider checking important information.
                    </div>
                </div>
            </div>
        </div>
    );
};

