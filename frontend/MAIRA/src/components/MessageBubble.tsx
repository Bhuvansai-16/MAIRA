import { cn } from "../lib/utils";
import { User, Bot } from "lucide-react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MessageBubbleProps {
    role: 'user' | 'agent';
    content: string;
}

export const MessageBubble = ({ role, content }: MessageBubbleProps) => {
    return (
        <div
            className={cn(
                "flex w-full items-start gap-4 p-4",
                role === "user" ? "flex-row-reverse" : "flex-row"
            )}
        >
            <div
                className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
                    role === "user"
                        ? "border-blue-500 bg-blue-500 text-white"
                        : "border-neutral-700 bg-neutral-800 text-white"
                )}
            >
                {role === "user" ? <User size={16} /> : <Bot size={16} />}
            </div>
            <div
                className={cn(
                    "flex max-w-[80%] flex-col gap-1 rounded-2xl px-4 py-3 text-sm shadow-sm",
                    role === "user"
                        ? "bg-blue-600 text-white rounded-tr-sm"
                        : "bg-neutral-800 text-white rounded-tl-sm border border-neutral-700"
                )}
            >
                <div className="prose prose-invert max-w-none text-sm leading-relaxed break-words">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {content}
                    </ReactMarkdown>
                </div>
            </div>
        </div>
    );
};
