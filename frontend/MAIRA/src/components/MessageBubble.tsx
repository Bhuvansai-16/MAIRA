import { useState, memo } from 'react';
import { cn } from "../lib/utils";
import { User, Shield, FileDown, Pencil, Check, X, Copy, CheckCircle2, ChevronLeft, ChevronRight, FileText } from "lucide-react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
import { BranchSwitcher } from './BranchSwitcher';
import { VerificationScore } from './VerificationScore';
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
    attachments?: { name: string; type: 'file' | 'image' }[];
    download?: {
        filename: string;
        data: string;
    };
    verification?: VerificationData;
    onEdit?: (index: number, newContent: string) => void;
    isStreaming?: boolean;
    // Version navigation props
    totalVersions?: number;
    currentVersionIndex?: number;
    onVersionChange?: (messageIndex: number, versionIndex: number) => void;
}

export const MessageBubble = memo(({ 
    role, 
    content, 
    status, 
    reasoning,
    messageIndex,
    attachments,
    download, 
    verification,
    onEdit,
    isStreaming = false,
    totalVersions = 1,
    currentVersionIndex = 0,
    onVersionChange
}: MessageBubbleProps) => {
    const [isEditing, setIsEditing] = useState(false);
    const [editContent, setEditContent] = useState(content);
    const [copied, setCopied] = useState(false);

    const displayContent = content
        .replace(/\[DOWNLOAD_DOCX\].*$/s, '')
        .replace(/\[DOWNLOAD_PDF\].*$/s, '')
        .replace(/\[VERIFICATION\].*$/s, '')
        .replace(/\[MODE:.*?\]/g, '')
        .replace(/\[SUBAGENT:.*?\]/g, '')
        .replace(/\[UPLOADED_FILES:.*?\]\n?/g, '')  // Strip uploaded files tag
        .replace(/\[USER MEMORY\][\s\S]*?\[\/USER MEMORY\]/g, '')  // Strip user memory context
        .replace(/<think>[\s\S]*?<\/think>/g, '')  // Strip reasoning tags from display
        .replace(/\[PERSONA:.*?\]/g, '')  // Strip persona tags from display
        .trim();

    const handleEdit = () => {
        if (onEdit && messageIndex !== undefined) {
            onEdit(messageIndex, editContent);
            setIsEditing(false);
            toast.success("Message updated");
        }
    };

    const handleCopy = () => {
        navigator.clipboard.writeText(displayContent);
        setCopied(true);
        toast.success("Copied to clipboard");
        setTimeout(() => setCopied(false), 2000);
    };

    const handleCancelEdit = () => {
        setEditContent(content);
        setIsEditing(false);
    };

    const handleDownload = (e: React.MouseEvent) => {
        e.preventDefault(); // Prevent default button behavior
        e.stopPropagation(); // Prevent bubbling
        
        if (!download || !download.data) {
            console.error("Download data is missing");
            alert("Download failed: No data available.");
            return;
        }

        console.log('=== DOWNLOAD DEBUG ===');
        console.log('Filename:', download.filename);
        console.log('Data length:', download.data.length);
        console.log('Data preview (first 100 chars):', download.data.substring(0, 100));

        try {
            // Clean base64 string - remove data URI prefix, whitespace, and newlines
            let base64Data = download.data.replace(/^data:.*,/, '').replace(/\s+/g, '').trim();
            
            // Validate base64 characters (should only contain A-Z, a-z, 0-9, +, /, =)
            const validBase64Regex = /^[A-Za-z0-9+/]*={0,2}$/;
            if (!validBase64Regex.test(base64Data)) {
                console.error("Invalid base64 characters detected!");
                const invalidChars = base64Data.match(/[^A-Za-z0-9+/=]/g);
                console.error("Invalid characters found:", invalidChars);
                alert(`Download failed: Invalid base64 encoding. Found invalid characters: ${invalidChars?.join(', ')}`);
                return;
            }
            
            // Validate base64 string length (must be multiple of 4)
            if (base64Data.length % 4 !== 0) {
                console.warn("Base64 string length is not multiple of 4, padding...");
                // Add padding if needed
                while (base64Data.length % 4 !== 0) {
                    base64Data += '=';
                }
            }

            console.log('Cleaned base64 length:', base64Data.length);
            console.log('Attempting to decode...');
            const byteCharacters = atob(base64Data);
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

            const blob = new Blob([byteArray], { type: mimeType });
            
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = download.filename;
            
            document.body.appendChild(a);
            a.click();
            
            // Cleanup
            window.setTimeout(() => {
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            }, 100);

            console.log('Download triggered successfully!');
        } catch (err) {
            console.error("Download failed:", err);
            alert(`Failed to download file: ${err instanceof Error ? err.message : String(err)}`);
        }
    };

    // Version navigation handlers
    const handlePrevVersion = () => {
        if (onVersionChange && messageIndex !== undefined && currentVersionIndex > 0) {
            onVersionChange(messageIndex, currentVersionIndex - 1);
        }
    };

    const handleNextVersion = () => {
        if (onVersionChange && messageIndex !== undefined && currentVersionIndex < totalVersions - 1) {
            onVersionChange(messageIndex, currentVersionIndex + 1);
        }
    };

    const hasMultipleVersions = totalVersions > 1;

    return (
        <div
            className={cn(
                "flex w-full items-start gap-5 group transition-all duration-500",
                role === "user" ? "flex-row-reverse" : "flex-row"
            )}
        >
            {/* Avatar with version indicator */}
            <div className="flex flex-col items-center gap-2">
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
                
                {/* Version Navigation - only show for user messages with multiple versions */}
                {role === "user" && hasMultipleVersions && !isEditing && (
                    <div className="ml-2">
                        <BranchSwitcher 
                            currentVersion={currentVersionIndex}
                            totalVersions={totalVersions}
                            onPrevious={handlePrevVersion}
                            onNext={handleNextVersion}
                        />
                    </div>
                )}
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
                        onClick={() => {
                            setEditContent(content);
                            setIsEditing(true);
                        }}
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
                            className="w-full min-h-[80px] p-0 rounded-none bg-transparent border-none text-black text-[15px] font-semibold resize-none focus:outline-none focus:ring-0 placeholder:text-neutral-400"
                            placeholder="Edit your message..."
                            aria-label="Edit message content"
                            autoFocus
                        />
                        <div className="flex justify-center gap-2 mt-2">
                             <button
                                onClick={handleCancelEdit}
                                className="px-4 py-2 rounded-full text-xs font-bold text-neutral-500 hover:text-black hover:bg-neutral-100 transition-all"
                            >
                                <X size={14} className="inline mr-1" />
                                Cancel
                            </button>
                            <button
                                onClick={handleEdit}
                                className="px-4 py-2 rounded-full text-xs font-bold bg-blue-600 text-white hover:bg-blue-700 transition-all shadow-lg shadow-blue-500/30"
                            >
                                <Check size={14} className="inline mr-1" />
                                Save & Regenerate
                            </button>
                        </div>
                    </div>
                ) : (
                    <>
                        {/* Attachment chips for user messages */}
                        {role === 'user' && attachments && attachments.length > 0 && (
                            <div className="flex flex-wrap gap-2 mb-1">
                                {attachments.map((att, idx) => (
                                    <div
                                        key={idx}
                                        className="flex items-center gap-2 bg-black/10 rounded-lg px-3 py-1.5"
                                    >
                                        <div className={cn(
                                            "p-1 rounded",
                                            att.type === 'image'
                                                ? "bg-purple-500/20 text-purple-600"
                                                : "bg-red-500/20 text-red-500"
                                        )}>
                                            {att.type === 'image' ? <ImageIcon size={14} /> : <FileText size={14} />}
                                        </div>
                                        <span className="text-xs font-medium truncate max-w-[150px]">{att.name}</span>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Status Indicator - shows during tool calls (only when no content AND no download) */}
                        {status && !displayContent && !download && (
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
                            "prose prose-invert max-w-none text-[15px] leading-relaxed break-words relative",
                            "prose-p:my-2 prose-headings:text-white prose-headings:font-black prose-headings:tracking-tight prose-headings:mt-6 prose-headings:mb-4",
                            "prose-strong:text-white prose-strong:font-bold",
                            "prose-code:text-blue-300 prose-code:bg-blue-500/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:font-mono prose-code:text-[0.9em]",
                            "prose-pre:bg-[#1A1A1A] prose-pre:border prose-pre:border-white/10 prose-pre:rounded-xl prose-pre:p-4",
                            "prose-ul:my-2 prose-ul:list-disc prose-ul:pl-4",
                            "prose-ol:my-2 prose-ol:list-decimal prose-ol:pl-4",
                            "prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline prose-a:font-medium",
                            "prose-blockquote:border-l-4 prose-blockquote:border-blue-500/50 prose-blockquote:bg-blue-500/5 prose-blockquote:px-4 prose-blockquote:py-1 prose-blockquote:rounded-r-lg prose-blockquote:not-italic prose-blockquote:text-neutral-300",
                            "prose-table:border-collapse prose-table:w-full prose-table:my-4 prose-table:text-sm",
                            "prose-th:border prose-th:border-white/10 prose-th:p-2 prose-th:bg-white/5 prose-th:text-left",
                            "prose-td:border prose-td:border-white/10 prose-td:p-2",
                            "prose-img:rounded-xl prose-img:shadow-lg",
                            role === "user" && "prose-p:text-black prose-strong:text-black prose-invert-none prose-headings:text-black"
                        )}>
                            {/* Copy button for agent messages */}
                            {role === 'agent' && displayContent && (
                                <button
                                    onClick={handleCopy}
                                    className="absolute -top-1 -right-1 p-1.5 rounded-lg text-neutral-500 hover:text-white hover:bg-white/10 opacity-0 group-hover:opacity-100 transition-all z-10"
                                    title="Copy content"
                                >
                                    {copied ? <CheckCircle2 size={14} className="text-green-500" /> : <Copy size={14} />}
                                </button>
                            )}
                            
                            {displayContent ? (
                                <ReactMarkdown 
                                    remarkPlugins={[remarkGfm]}
                                    components={{
                                        // Custom link component to open in new tab and style differently if citation
                                        a: ({ node: _node, ...props }) => {
                                            // _node unused
                                            const isCitation = props.href?.includes('#citation');
                                            return (
                                                <a 
                                                    {...props} 
                                                    target="_blank" 
                                                    rel="noopener noreferrer"
                                                    className={cn(
                                                        props.className,
                                                        isCitation && "inline-flex items-center justify-center w-4 h-4 rounded-full bg-blue-500/20 text-blue-400 text-[10px] font-bold ml-0.5 align-super no-underline hover:bg-blue-500/30"
                                                    )}
                                                >
                                                    {props.children}
                                                </a>
                                            );
                                        }
                                    }}
                                >
                                    {displayContent}
                                </ReactMarkdown>
                            ) : (
                                !status && !reasoning && !download && (
                                    <div className="flex items-center gap-2 text-neutral-500 italic">
                                        <motion.span 
                                            animate={{ opacity: [0.4, 1, 0.4] }}
                                            transition={{ repeat: Infinity, duration: 1.5 }}
                                        >
                                            Thinking...
                                        </motion.span>
                                    </div>
                                )
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
