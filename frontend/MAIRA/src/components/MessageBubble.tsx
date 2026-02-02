import { useState, memo } from 'react';
import { cn } from "../lib/utils";
import { User, Shield, FileDown, Pencil, Check, X } from "lucide-react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { VerificationScore, type VerificationDetails } from './VerificationScore';
import { VerificationBadge, type VerificationStatus } from './VerificationBadge';
import { ReasoningBlock } from './ReasoningBlock';
import type { VerificationData } from '../types/agent';

interface MessageBubbleProps {
    role: 'user' | 'agent';
    content: string;
    thought?: string;
    reasoning?: string;
    status?: string;
    messageIndex?: number;
    download?: {
        filename: string;
        data: string;
    };
    verification?: VerificationData;
    onEdit?: (index: number, newContent: string) => void;
    isStreaming?: boolean;
}

export const MessageBubble = memo(({ 
    role, 
    content, 
    status, 
    reasoning,
    messageIndex,
    download, 
    verification,
    onEdit,
    isStreaming = false
}: MessageBubbleProps) => {
    const [isEditing, setIsEditing] = useState(false);
    const [editContent, setEditContent] = useState(content);

    const displayContent = content
        .replace(/\[DOWNLOAD_DOCX\].*$/s, '')
        .replace(/\[DOWNLOAD_PDF\].*$/s, '')
        .replace(/\[VERIFICATION\].*$/s, '')
        .replace(/\[MODE:.*?\]/g, '')
        .replace(/\[SUBAGENT:.*?\]/g, '')
        .replace(/<think>[\s\S]*?<\/think>/g, '')  // Strip reasoning tags from display
        .trim();

    const handleEdit = () => {
        if (onEdit && messageIndex !== undefined) {
            onEdit(messageIndex, editContent);
            setIsEditing(false);
        }
    };

    const handleCancelEdit = () => {
        setEditContent(content);
        setIsEditing(false);
    };

    const handleDownload = (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent bubbling
        if (!download) return;

        console.log('=== DOWNLOAD DEBUG ===');
        console.log('Filename:', download.filename);
        console.log('Data length:', download.data.length);
        console.log('Data first 100 chars:', download.data.substring(0, 100));
        console.log('Data last 100 chars:', download.data.substring(download.data.length - 100));

        try {
            // Clean base64 string
            const base64Data = download.data.replace(/^data:.*,/, '').replace(/\s/g, '');
            console.log('Cleaned base64 length:', base64Data.length);
            console.log('Cleaned first 50:', base64Data.substring(0, 50));

            const byteCharacters = atob(base64Data);
            console.log('Decoded byte characters length:', byteCharacters.length);

            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);

            // Determine MIME type
            const isPdf = download.filename.toLowerCase().endsWith('.pdf');
            const mimeType = isPdf
                ? 'application/pdf'
                : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

            console.log('MIME type:', mimeType);
            console.log('File size:', byteArray.length, 'bytes');

            const blob = new Blob([byteArray], { type: mimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = download.filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            console.log('Download successful!');
        } catch (err) {
            console.error("Download failed:", err);
            console.error("Error details:", err instanceof Error ? err.message : String(err));
            alert("Failed to download file. The data might be corrupted.");
        }
    };

    return (
        <div
            className={cn(
                "flex w-full items-start gap-5 group transition-all duration-500",
                role === "user" ? "flex-row-reverse" : "flex-row"
            )}
        >
            <div
                className={cn(
                    "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border-2 shadow-xl ring-offset-2 ring-offset-black transition-all group-hover:scale-110",
                    role === "user"
                        ? "border-blue-600/30 bg-blue-600 text-white ring-blue-600/20"
                        : "border-white/10 bg-[#121212] text-white ring-white/10"
                )}
            >
                {role === "user" ? <User size={18} strokeWidth={2.5} /> : <Shield size={18} strokeWidth={2.5} className="text-blue-500" />}
            </div>

            <div
                className={cn(
                    "flex max-w-[85%] flex-col gap-3 rounded-[24px] px-6 py-5 text-sm transition-all duration-300 relative",
                    role === "user"
                        ? "bg-white text-black font-semibold shadow-2xl shadow-white/5 rounded-tr-sm"
                        : "bg-[#121212] border border-white/5 text-[#e5e5e5] rounded-tl-sm hover:border-white/10 shadow-2xl shadow-black/50"
                )}
            >
                {/* Edit Button for user messages */}
                {role === "user" && onEdit && !isEditing && (
                    <button
                        onClick={() => setIsEditing(true)}
                        className="absolute -left-10 top-4 p-2 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-white/10 text-neutral-500 hover:text-white transition-all"
                        title="Edit message"
                    >
                        <Pencil size={14} />
                    </button>
                )}

                {/* Editing UI */}
                {isEditing && role === "user" ? (
                    <div className="flex flex-col gap-3">
                        <textarea
                            value={editContent}
                            onChange={(e) => setEditContent(e.target.value)}
                            className="w-full min-h-[80px] p-3 rounded-xl bg-black/50 border border-white/20 text-white text-sm resize-none focus:outline-none focus:border-blue-500"
                            placeholder="Edit your message..."
                            aria-label="Edit message content"
                            autoFocus
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={handleCancelEdit}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-neutral-400 hover:text-white hover:bg-white/10 transition-all"
                            >
                                <X size={14} />
                                Cancel
                            </button>
                            <button
                                onClick={handleEdit}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-blue-600 text-white hover:bg-blue-500 transition-all"
                            >
                                <Check size={14} />
                                Save & Regenerate
                            </button>
                        </div>
                    </div>
                ) : (
                    <>
                        {/* Status Indicator - shows during tool calls */}
                        {status && !displayContent && (
                            <div className="flex items-center gap-3">
                                <div className="flex items-center gap-1">
                                    <div className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.3s]"></div>
                                    <div className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.15s]"></div>
                                    <div className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-bounce"></div>
                                </div>
                                <span className="text-[10px] font-black uppercase tracking-[0.15em] text-neutral-500">
                                    {status}
                                </span>
                            </div>
                        )}

                        {/* Reasoning Block - shows agent's thinking process */}
                        {reasoning && role === 'agent' && (
                            <ReasoningBlock 
                                content={reasoning} 
                                isStreaming={isStreaming && !displayContent}
                            />
                        )}

                        {/* Main Content */}
                        <div className={cn(
                            "prose prose-invert max-w-none text-[15px] leading-relaxed break-words prose-p:my-2 prose-headings:text-white prose-headings:font-black prose-headings:tracking-tight prose-strong:text-white prose-strong:font-black prose-code:text-blue-400 prose-code:bg-blue-400/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:before:content-none prose-code:after:content-none prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline",
                            role === "user" && "prose-p:text-black prose-strong:text-black prose-invert-none"
                        )}>
                            {displayContent ? (
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {displayContent}
                                </ReactMarkdown>
                            ) : (
                                !status && !reasoning && !download && <span className="text-neutral-500 italic">Thinking...</span>
                            )}
                        </div>

                        {download && (
                            <div className="mt-4 pt-4 border-t border-white/5">
                                <button
                                    onClick={handleDownload}
                                    className={`group/dl relative flex w-full items-center justify-between gap-4 overflow-hidden rounded-2xl p-5 border transition-all duration-500 ${download.filename.toLowerCase().endsWith('.pdf')
                                            ? 'bg-gradient-to-br from-red-600/10 to-rose-600/10 border-red-500/20 hover:border-red-500/40 hover:shadow-[0_0_30px_rgba(239,68,68,0.15)]'
                                            : 'bg-gradient-to-br from-blue-600/10 to-purple-600/10 border-blue-500/20 hover:border-blue-500/40 hover:shadow-[0_0_30px_rgba(59,130,246,0.15)]'
                                        }`}
                                >
                                    <div className={`absolute inset-0 bg-gradient-to-r to-transparent opacity-0 group-hover/dl:opacity-100 transition-opacity ${download.filename.toLowerCase().endsWith('.pdf') ? 'from-red-600/5' : 'from-blue-600/5'
                                        }`} />

                                    <div className="flex items-center gap-4 relative z-10">
                                        <div className={`flex h-12 w-12 items-center justify-center rounded-xl group-hover/dl:scale-110 group-hover/dl:text-white transition-all duration-500 active:scale-95 ${download.filename.toLowerCase().endsWith('.pdf')
                                                ? 'bg-red-600/20 text-red-400 group-hover/dl:bg-red-600'
                                                : 'bg-blue-600/20 text-blue-400 group-hover/dl:bg-blue-600'
                                            }`}>
                                            <FileDown size={24} />
                                        </div>
                                        <div className="text-left">
                                            <div className={`text-[10px] font-black uppercase tracking-widest mb-0.5 ${download.filename.toLowerCase().endsWith('.pdf') ? 'text-red-400/80' : 'text-blue-400/80'
                                                }`}>
                                                {download.filename.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOCX'} Document Ready
                                            </div>
                                            <div className={`font-bold text-white tracking-tight text-base transition-colors ${download.filename.toLowerCase().endsWith('.pdf') ? 'group-hover/dl:text-red-100' : 'group-hover/dl:text-blue-100'
                                                }`}>
                                                Research Report
                                            </div>
                                            <div className="text-xs text-neutral-500 truncate max-w-[200px] font-medium">{download.filename}</div>
                                        </div>
                                    </div>

                                    <div className={`relative z-10 flex h-10 w-10 items-center justify-center rounded-full border group-hover/dl:translate-x-1 transition-all ${download.filename.toLowerCase().endsWith('.pdf')
                                            ? 'border-red-500/30 text-red-400 group-hover/dl:bg-red-600/20 group-hover/dl:border-red-500/50'
                                            : 'border-blue-500/30 text-blue-400 group-hover/dl:bg-blue-600/20 group-hover/dl:border-blue-500/50'
                                        }`}>
                                        <FileDown size={18} className="rotate-[-90deg]" />
                                    </div>
                                </button>
                            </div>
                        )}
                        {/* Verification Score Display */}
                        {verification && role === 'agent' && (
                            <div className="mt-4 pt-4 border-t border-white/5">
                                <VerificationScore 
                                    verification={{
                                        overallScore: verification.overallScore,
                                        status: verification.status as VerificationStatus,
                                        citationScore: verification.citationScore,
                                        factCheckScore: verification.factCheckScore,
                                        qualityScore: verification.qualityScore,
                                        completenessScore: verification.completenessScore,
                                        validCitations: verification.validCitations,
                                        totalCitations: verification.totalCitations,
                                        verifiedFacts: verification.verifiedFacts,
                                        totalFacts: verification.totalFacts,
                                        issues: verification.issues,
                                        timestamp: verification.timestamp
                                    }}
                                />
                            </div>
                        )}

                        {/* Inline verification badge for streaming messages */}
                        {verification && verification.status === 'VERIFYING' && !displayContent && (
                            <div className="flex items-center gap-2 mt-2">
                                <VerificationBadge status="VERIFYING" />
                            </div>
                        )}                    </>
                )}
            </div>
        </div>
    );
});
