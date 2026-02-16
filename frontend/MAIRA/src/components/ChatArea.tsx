import { useState, useRef, useEffect } from "react";
import { Plus, Send, Mic, MicOff, Sparkles, Shield, GitBranch, BookOpen, Square, FileText, Image as ImageIcon, X, Loader2, Home } from "lucide-react";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { MessageBubble } from "./MessageBubble";
import { DeepResearchProgress } from "./DeepResearchProgress";
import { TimelineView } from "./TimelineView";
import { ModelSelector } from "./ModelSelector";
import { SitesSelector } from "./SitesSelector";
import { PersonaDropdown } from "./PersonaDropdown";
import { cn } from "../lib/utils";
import { useThreads } from "../hooks/useThreads";
import { useNavigate } from "react-router-dom";

type AttachmentStatus = 'uploading' | 'success' | 'error';

interface Attachment {
    id: string;
    file: File;
    type: 'file' | 'image';
    status: AttachmentStatus;
    previewUrl?: string; // For images
}

export const ChatArea = () => {
    const { currentMessages, isLoading, sendMessage, stopStream, currentThreadId, deepResearch, setDeepResearch, literatureSurvey, setLiteratureSurvey, editMessage, setMessageVersion, persona, setPersona, sites, setSites, uploadFile, uploadImage, customPersonas, addCustomPersona, deleteCustomPersona, saveSites, isSiteRestrictionEnabled, setIsSiteRestrictionEnabled } = useThreads();
    const navigate = useNavigate();
    const [input, setInput] = useState("");
    const [attachments, setAttachments] = useState<Attachment[]>([]);
    const [isTimelineOpen, setIsTimelineOpen] = useState(false);
    const [showAttachMenu, setShowAttachMenu] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const imageInputRef = useRef<HTMLInputElement>(null);

    const removeAttachment = (id: string) => {
        setAttachments(prev => prev.filter(a => a.id !== id));
    };

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setShowAttachMenu(false);

        const newAttachment: Attachment = {
            id: Math.random().toString(36).substring(7),
            file,
            type: 'file',
            status: 'uploading'
        };

        setAttachments(prev => [...prev, newAttachment]);

        try {
            await uploadFile(file);
            setAttachments(prev => prev.map(a =>
                a.id === newAttachment.id ? { ...a, status: 'success' } : a
            ));
        } catch (error) {
            console.error(error);
            setAttachments(prev => prev.map(a =>
                a.id === newAttachment.id ? { ...a, status: 'error' } : a
            ));
        }

        // Reset input
        if (fileInputRef.current) fileInputRef.current.value = "";
    };

    const handleImageSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setShowAttachMenu(false);

        const previewUrl = URL.createObjectURL(file);
        const newAttachment: Attachment = {
            id: Math.random().toString(36).substring(7),
            file,
            type: 'image',
            status: 'uploading',
            previewUrl
        };

        setAttachments(prev => [...prev, newAttachment]);

        try {
            await uploadImage(file);
            setAttachments(prev => prev.map(a =>
                a.id === newAttachment.id ? { ...a, status: 'success' } : a
            ));
        } catch (error) {
            console.error(error);
            setAttachments(prev => prev.map(a =>
                a.id === newAttachment.id ? { ...a, status: 'error' } : a
            ));
        }

        // Reset input
        if (imageInputRef.current) imageInputRef.current.value = "";
    };

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
        // Capture successful attachments to show in the message bubble
        const successAttachments = attachments
            .filter(a => a.status === 'success')
            .map(a => ({ name: a.file.name, type: a.type }));

        setInput(""); // Clear input early
        setAttachments([]); // Clear attachment chips
        await sendMessage(userMessage, undefined, successAttachments.length > 0 ? successAttachments : undefined);
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
                    <button
                        onClick={() => navigate('/')}
                        className="flex h-10 w-10 items-center justify-center rounded-full bg-white/5 border border-white/10 text-neutral-400 hover:text-white hover:bg-white/10 transition-all group"
                        title="Back to Home"
                    >
                        <Home size={18} className="group-hover:scale-110 transition-transform" />
                    </button>
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
                    {/* ModelSelector moved to footer */}
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
                            {currentMessages.map((msg, index) => {
                                // When deep research is active, hide the streaming placeholder
                                // (DeepResearchProgress replaces it below)
                                if (deepResearch && isLoading && msg.type === 'streaming') {
                                    return null;
                                }
                                return (
                                    <div
                                        key={msg.message_id || `${index}-${msg.currentVersionIndex || 0}`}
                                        className="animate-slide-up"
                                    >
                                        <MessageBubble
                                            role={msg.role}
                                            content={msg.content}
                                            thought={msg.thought}
                                            status={msg.status}
                                            attachments={msg.attachments}
                                            download={msg.download}
                                            verification={msg.verification}
                                            // reasoning feature removed per user request
                                            messageIndex={index}
                                            onEdit={editMessage}
                                            isStreaming={msg.type === 'streaming'}
                                            totalVersions={msg.versions?.length || 1}
                                            currentVersionIndex={msg.currentVersionIndex || 0}
                                            onVersionChange={setMessageVersion}
                                        />
                                    </div>
                                );
                            })}

                            {/* Deep Research: show phased progress UI instead of plain MessageBubble */}
                            {isLoading && deepResearch && currentMessages.some(m => m.type === 'streaming') && (
                                <div className="animate-slide-up">
                                    <div className="flex w-full items-start gap-5">
                                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border-2 border-white/10 bg-[#121212] text-white ring-offset-2 ring-offset-black shadow-xl ring-white/10">
                                            <Shield size={18} strokeWidth={2.5} className="text-blue-500" />
                                        </div>
                                        <DeepResearchProgress
                                            isActive={true}
                                            status={currentMessages.find(m => m.type === 'streaming')?.status}
                                            progress={currentMessages.find(m => m.type === 'streaming')?.progress}
                                        />
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </main>

            {/* Input Area */}
            <footer className="p-6 md:p-10 relative z-20">
                <div className="mx-auto max-w-3xl flex flex-col gap-4">
                    {/* Floating Prompt Bar */}
                    <div className="relative group/input">
                        {/* Attachments List */}
                        {attachments.length > 0 && (
                            <div className="absolute bottom-full left-0 w-full mb-4 flex flex-wrap gap-2 px-1 z-10">
                                {attachments.map((attachment) => (
                                    <div key={attachment.id} className="relative group/attachment flex items-center gap-3 bg-[#1A1A1A]/90 backdrop-blur-md border border-white/10 rounded-xl p-2 pr-8 shadow-lg animate-in fade-in slide-in-from-bottom-2 duration-200">
                                        {attachment.type === 'image' && attachment.previewUrl ? (
                                            <div className="h-10 w-10 rounded-lg overflow-hidden bg-black/50 shrink-0 border border-white/5">
                                                <img src={attachment.previewUrl} alt="Preview" className="h-full w-full object-cover" />
                                            </div>
                                        ) : (
                                            <div className="h-10 w-10 rounded-lg flex items-center justify-center bg-blue-500/10 text-blue-400 shrink-0 border border-blue-500/20">
                                                <FileText size={20} />
                                            </div>
                                        )}

                                        <div className="flex flex-col min-w-[60px] max-w-[180px]">
                                            <span className="text-xs text-white truncate font-medium" title={attachment.file.name}>
                                                {attachment.file.name}
                                            </span>
                                            <span className="text-[10px] text-neutral-400">
                                                {attachment.status === 'uploading' ? 'Uploading...' : `${(attachment.file.size / 1024).toFixed(0)} KB`}
                                            </span>
                                        </div>

                                        {/* Status Indicator */}
                                        <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                            {attachment.status === 'uploading' && (
                                                <Loader2 size={16} className="animate-spin text-blue-400" />
                                            )}
                                            {attachment.status === 'error' && (
                                                <div className="text-red-400 text-[10px] font-medium">Error</div>
                                            )}
                                        </div>

                                        {/* Remove Button */}
                                        <button
                                            onClick={() => removeAttachment(attachment.id)}
                                            className="absolute -top-2 -right-2 p-1 rounded-full bg-neutral-800 text-neutral-400 hover:text-white border border-neutral-700 shadow-md opacity-0 group-hover/attachment:opacity-100 transition-all hover:bg-red-500/20 hover:border-red-500/50 hover:text-red-400"
                                        >
                                            <X size={12} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Glow effect on focus */}
                        <div className="absolute -inset-0.5 bg-gradient-to-r from-violet-600 to-indigo-600 rounded-full opacity-20 group-focus-within/input:opacity-100 blur transition-all duration-500" />

                        <div className="relative z-20 flex items-center gap-2 rounded-full border border-violet-500/30 bg-[#0A0A0A] p-2 shadow-2xl shadow-violet-900/20 backdrop-blur-xl transition-all duration-300 group-focus-within/input:border-violet-500/80 group-focus-within/input:shadow-violet-500/20">

                            {/* Attachment Button */}
                            <div className="relative">
                                <button
                                    onClick={() => setShowAttachMenu(!showAttachMenu)}
                                    className={cn(
                                        "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-neutral-800/50 text-neutral-400 hover:bg-neutral-800 hover:text-white transition-all active:scale-95",
                                        showAttachMenu && "bg-neutral-800 text-white rotate-45"
                                    )}
                                    title="Add attachment"
                                >
                                    <Plus size={20} />
                                </button>

                                {/* Attachment Menu */}
                                {showAttachMenu && (
                                    <div className="absolute bottom-14 left-0 flex flex-col gap-2 p-2 rounded-xl bg-[#0A0A0A] border border-neutral-800 shadow-xl shadow-black/50 overflow-hidden animate-slide-up origin-bottom-left z-50 min-w-[140px]">
                                        <button
                                            onClick={() => {
                                                fileInputRef.current?.click();
                                            }}
                                            className="flex items-center gap-3 px-3 py-2 text-sm text-neutral-400 hover:text-white hover:bg-neutral-800/50 rounded-lg transition-colors text-left"
                                        >
                                            <div className="p-1.5 rounded-full bg-blue-500/10 text-blue-400">
                                                <FileText size={16} />
                                            </div>
                                            <span>Document</span>
                                        </button>
                                        <button
                                            onClick={() => {
                                                imageInputRef.current?.click();
                                            }}
                                            className="flex items-center gap-3 px-3 py-2 text-sm text-neutral-400 hover:text-white hover:bg-neutral-800/50 rounded-lg transition-colors text-left"
                                        >
                                            <div className="p-1.5 rounded-full bg-purple-500/10 text-purple-400">
                                                <ImageIcon size={16} />
                                            </div>
                                            <span>Image</span>
                                        </button>
                                    </div>
                                )}

                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    className="hidden"
                                    accept=".pdf,.txt,.md,.csv,.json,.doc,.docx"
                                    onChange={handleFileSelect}
                                    aria-label="Upload document"
                                />
                                <input
                                    type="file"
                                    ref={imageInputRef}
                                    className="hidden"
                                    accept="image/png,image/jpeg,image/webp,image/gif"
                                    onChange={handleImageSelect}
                                    aria-label="Upload image"
                                />
                            </div>

                            {/* Text Input */}
                            <textarea
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder="Ask me anything about LangChain..."
                                className="flex-1 resize-none bg-transparent px-2 py-2.5 text-sm text-white placeholder-neutral-500 focus:outline-none scrollbar-hide font-medium leading-relaxed min-h-[44px] max-h-[120px]"
                                rows={1}
                                aria-label="Message input"
                            />

                            {/* Right Actions */}
                            <div className="flex items-center gap-1 pr-1">
                                {/* Voice Input */}
                                {hasRecognition && (
                                    <button
                                        onClick={isListening ? stopListening : startListening}
                                        className={cn(
                                            "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full transition-all duration-300 active:scale-95",
                                            isListening
                                                ? "bg-red-500/20 text-red-500 animate-pulse ring-1 ring-red-500/20"
                                                : "text-neutral-400 hover:bg-neutral-800 hover:text-white"
                                        )}
                                        title={isListening ? "Stop listening" : "Start voice input"}
                                    >
                                        {isListening ? <MicOff size={18} /> : <Mic size={18} />}
                                    </button>
                                )}

                                {/* Send / Stop Button */}
                                {isLoading ? (
                                    <button
                                        onClick={stopStream}
                                        className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-red-500/10 text-red-500 hover:bg-red-500/20 active:scale-95 transition-all animate-scaled-in border border-red-500/20"
                                        title="Stop generating"
                                    >
                                        <Square size={16} className="fill-current" />
                                    </button>
                                ) : (
                                    input.trim() && (
                                        <button
                                            onClick={handleSend}
                                            className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-violet-600 text-white shadow-lg shadow-violet-600/20 hover:bg-violet-500 hover:scale-105 active:scale-95 transition-all animate-scaled-in"
                                            title="Send message"
                                        >
                                            <Send size={16} className="-translate-x-0.5 translate-y-0.5" />
                                        </button>
                                    )
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Controls Row (Below Bar) */}
                    <div className="flex flex-nowrap items-center justify-between gap-4 px-2">
                        {/* Model Selector */}
                        <ModelSelector />

                        {/* Research Toggles */}
                        <div className="flex items-center gap-2 overflow-x-auto pb-1 min-w-0 scrollbar-hide no-scrollbar mask-gradient-right">
                            {/* Deep Research */}
                            <button
                                onClick={() => setDeepResearch(!deepResearch)}
                                className={cn(
                                    "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-[10px] font-bold uppercase tracking-wider transition-all whitespace-nowrap select-none",
                                    deepResearch
                                        ? "bg-blue-500/10 border-blue-500/30 text-blue-400"
                                        : "bg-white/5 border-white/5 text-neutral-500 hover:bg-white/10 hover:text-white"
                                )}
                            >
                                <Sparkles size={12} />
                                <span>Deep Research</span>
                            </button>

                            {/* Lit Survey */}
                            <button
                                onClick={() => setLiteratureSurvey(!literatureSurvey)}
                                className={cn(
                                    "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-[10px] font-bold uppercase tracking-wider transition-all whitespace-nowrap select-none",
                                    literatureSurvey
                                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                                        : "bg-white/5 border-white/5 text-neutral-500 hover:bg-white/10 hover:text-white"
                                )}
                            >
                                <BookOpen size={12} />
                                <span>Survey</span>
                            </button>

                            {/* Deep Research sub-options: Sites + Persona (only visible when Deep Research OR Lit Survey is ON) */}
                            {(deepResearch || literatureSurvey) && (
                                <>
                                    {/* Sites Selector */}
                                    <SitesSelector
                                        sites={sites}
                                        setSites={(newSites) => { setSites(newSites); saveSites(newSites); }}
                                        isSiteRestrictionEnabled={isSiteRestrictionEnabled}
                                        setIsSiteRestrictionEnabled={setIsSiteRestrictionEnabled}
                                    />

                                    {/* Persona Dropdown (Only for Deep Research) */}
                                    {deepResearch && (
                                        <PersonaDropdown persona={persona} setPersona={setPersona} customPersonas={customPersonas} onAddPersona={addCustomPersona} onDeletePersona={deleteCustomPersona} />
                                    )}
                                </>
                            )}


                        </div>
                    </div>

                    <p className="mt-2 text-center text-[10px] font-bold text-neutral-600 uppercase tracking-[0.2em] animate-fade-in opacity-50 hover:opacity-100 transition-opacity">
                        MAIRA v1.1 • Research Agent
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

