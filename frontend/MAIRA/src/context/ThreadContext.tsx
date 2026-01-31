import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import type { ReactNode } from 'react';
import axios from 'axios';

const API_BASE = 'http://localhost:8000';

// Types
export interface Thread {
    thread_id: string;
    title: string;
    created_at: string;
    updated_at: string;
}

export interface Message {
    role: 'user' | 'agent';
    content: string;
    thought?: string;
    status?: string;
    type?: 'streaming' | 'final';
    download?: {
        filename: string;
        data: string;  // Base64 encoded
    };
}

interface ThreadContextType {
    threads: Thread[];
    currentThreadId: string | null;
    currentMessages: Message[];
    isLoading: boolean;
    isLoadingThreads: boolean;
    deepResearch: boolean;
    // Actions
    createThread: (title?: string) => Promise<Thread>;
    selectThread: (threadId: string) => Promise<void>;
    deleteThread: (threadId: string) => Promise<void>;
    refreshThreads: () => Promise<void>;
    sendMessage: (prompt: string) => Promise<void>;
    startNewChat: () => void;
    setDeepResearch: (enabled: boolean) => void;
}

const ThreadContext = createContext<ThreadContextType | null>(null);

export const useThreads = () => {
    const context = useContext(ThreadContext);
    if (!context) {
        throw new Error('useThreads must be used within a ThreadProvider');
    }
    return context;
};

interface ThreadProviderProps {
    children: ReactNode;
}

export const ThreadProvider = ({ children }: ThreadProviderProps) => {
    const [threads, setThreads] = useState<Thread[]>([]);
    const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
    const [currentMessages, setCurrentMessages] = useState<Message[]>([
        { role: 'agent', content: "Hello! I am MAIRA, your advanced research agent. How can I help you today?" }
    ]);
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingThreads, setIsLoadingThreads] = useState(false);
    const [deepResearch, setDeepResearch] = useState(false);

    // Fetch all threads on mount
    const refreshThreads = useCallback(async () => {
        setIsLoadingThreads(true);
        try {
            const response = await axios.get(`${API_BASE}/threads`);
            setThreads(response.data);
        } catch (error) {
            console.error('Failed to fetch threads:', error);
        } finally {
            setIsLoadingThreads(false);
        }
    }, []);

    useEffect(() => {
        refreshThreads();
    }, [refreshThreads]);

    // Create a new thread
    const createThread = useCallback(async (title?: string): Promise<Thread> => {
        const response = await axios.post(`${API_BASE}/threads`, { title });
        const newThread = response.data;
        setThreads(prev => [newThread, ...prev]);
        return newThread;
    }, []);

    // Select a thread and load its messages
    const selectThread = useCallback(async (threadId: string) => {
        setCurrentThreadId(threadId);
        setIsLoading(true);

        try {
            const response = await axios.get(`${API_BASE}/threads/${threadId}/messages`);
            const messages = response.data.messages || [];

            // Convert backend message format to frontend format
            const formattedMessages: Message[] = messages.map((msg: any) => {
                const isUser = msg.type === 'human' || msg.role === 'user';
                const isTool = msg.type === 'tool' || msg.role === 'tool';

                // Skip tool messages UNLESS they contain a download
                if (isTool) {
                    const hasDownload = typeof msg.content === 'string' &&
                        (msg.content.includes('[DOWNLOAD_DOCX]') || msg.content.includes('[DOWNLOAD_PDF]'));
                    if (!hasDownload) return null;
                }

                let content = '';
                if (typeof msg.content === 'string') {
                    content = msg.content;
                } else if (Array.isArray(msg.content)) {
                    content = msg.content
                        .map((c: any) => typeof c === 'string' ? c : (c.text || ''))
                        .join('');
                }

                if (!content.trim()) return null;

                let downloadData;

                // Check for download markers in history
                const pdfMarker = '[DOWNLOAD_PDF]';
                const docxMarker = '[DOWNLOAD_DOCX]';

                let marker = null;
                if (content.includes(pdfMarker)) marker = pdfMarker;
                else if (content.includes(docxMarker)) marker = docxMarker;

                if (marker) {
                    try {
                        const index = content.indexOf(marker);
                        const jsonPart = content.substring(index + marker.length).trim();
                        const lastBrace = jsonPart.lastIndexOf('}');
                        if (lastBrace !== -1) {
                            const jsonStr = jsonPart.substring(0, lastBrace + 1);
                            downloadData = JSON.parse(jsonStr);
                            // Clean content for display
                            content = content.substring(0, index).trim() || 'Report generated successfully! Click below to download.';
                        }
                    } catch (e) {
                        console.warn('Failed to parse historical download:', e);
                    }
                }

                return {
                    role: isUser ? 'user' : 'agent',
                    content: content,
                    download: downloadData
                } as Message;
            }).filter(Boolean) as Message[];

            // Add welcome message if no messages
            if (formattedMessages.length === 0) {
                formattedMessages.push({
                    role: 'agent',
                    content: "Hello! I am MAIRA, your advanced research agent. How can I help you today?"
                });
            }

            setCurrentMessages(formattedMessages);
        } catch (error) {
            console.error('Failed to load thread messages:', error);
            setCurrentMessages([
                { role: 'agent', content: "Hello! I am MAIRA, your advanced research agent. How can I help you today?" }
            ]);
        } finally {
            setIsLoading(false);
        }
    }, []);

    // Delete a thread
    const deleteThread = useCallback(async (threadId: string) => {
        try {
            await axios.delete(`${API_BASE}/threads/${threadId}`);
            setThreads(prev => prev.filter(t => t.thread_id !== threadId));

            // If deleted thread was current, reset to new chat
            if (currentThreadId === threadId) {
                setCurrentThreadId(null);
                setCurrentMessages([
                    { role: 'agent', content: "Hello! I am MAIRA, your advanced research agent. How can I help you today?" }
                ]);
            }
        } catch (error) {
            console.error('Failed to delete thread:', error);
        }
    }, [currentThreadId]);

    // Start a new chat
    const startNewChat = useCallback(() => {
        setCurrentThreadId(null);
        setCurrentMessages([
            { role: 'agent', content: "Hello! I am MAIRA, your advanced research agent. How can I help you today?" }
        ]);
    }, []);

    // Send a message with SSE streaming
    const sendMessage = useCallback(async (prompt: string) => {
        if (!prompt.trim() || isLoading) return;

        // Add user message immediately
        setCurrentMessages(prev => [...prev, { role: 'user', content: prompt }]);
        setIsLoading(true);

        let newThreadId = currentThreadId;
        let accumulatedContent = '';
        let buffer = ''; // Buffer for incomplete SSE lines
        let downloadData: { filename: string; data: string } | undefined = undefined;
        let responseComplete = false; // Track when we have a complete response

        // Helper to parse download markers from content - relaxed parsing
        const parseDownloadContent = (content: string): { cleanContent: string; download?: { filename: string; data: string } } => {
            // Check for both markers
            const pdfMarker = '[DOWNLOAD_PDF]';
            const docxMarker = '[DOWNLOAD_DOCX]';

            let marker = null;
            if (content.includes(pdfMarker)) marker = pdfMarker;
            else if (content.includes(docxMarker)) marker = docxMarker;

            if (marker) {
                const index = content.indexOf(marker);

                try {
                    // Extract potential JSON part (everything after marker)
                    const jsonPart = content.substring(index + marker.length).trim();
                    // Find the end of the JSON object (last closing brace)
                    const lastBrace = jsonPart.lastIndexOf('}');

                    if (lastBrace !== -1) {
                        const jsonStr = jsonPart.substring(0, lastBrace + 1);
                        const download = JSON.parse(jsonStr);

                        // Clean content by removing the marker and JSON
                        const cleanContent = content.substring(0, index).trim() || 'Report generated successfully! Click below to download.';
                        console.log("Download parsed successfully:", download.filename);
                        return { cleanContent, download };
                    }
                } catch (e) {
                    console.warn('Failed to parse download data JSON:', e);
                }
            }

            return { cleanContent: content };
        };

        try {
            const response = await fetch(`${API_BASE}/run-agent`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt, thread_id: currentThreadId, deep_research: deepResearch })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) {
                throw new Error('No response body reader available');
            }

            // Add placeholder for streaming response with loading indicator
            setCurrentMessages(prev => [...prev, { role: 'agent', content: '', status: 'Thinking...', type: 'streaming' }]);

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const text = decoder.decode(value, { stream: true });
                buffer += text;

                // Process complete lines
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            console.log('SSE data:', data); // Debug log

                            if (data.type === 'init' && data.thread_id) {
                                newThreadId = data.thread_id;
                                if (!currentThreadId) {
                                    setCurrentThreadId(newThreadId);
                                }
                            } else if (data.type === 'update' && data.messages) {
                                // Process messages from the update
                                for (const msg of data.messages) {
                                    console.log('Processing msg:', msg); // Debug log

                                    // Helper to extract content (handles array format from Gemini)
                                    const extractContent = (content: any): string => {
                                        if (typeof content === 'string') return content;
                                        if (Array.isArray(content)) {
                                            return content
                                                .map((c: any) => c.text || c.content || '')
                                                .join('');
                                        }
                                        return '';
                                    };

                                    // Check if this is a tool call (show status)
                                    if (msg.tool_calls && msg.tool_calls.length > 0) {
                                        const toolNames = msg.tool_calls.map((tc: any) => tc.name).join(', ');
                                        const status = `🔍 Researching... (${toolNames})`;

                                        setCurrentMessages(prev => {
                                            const updated = [...prev];
                                            const lastIdx = updated.length - 1;
                                            if (updated[lastIdx]?.type === 'streaming') {
                                                updated[lastIdx] = { ...updated[lastIdx], status };
                                            }
                                            return updated;
                                        });
                                    }
                                    else if (msg.content && msg.type !== 'human') {
                                        const textContent = extractContent(msg.content);
                                        const cleanContent = textContent
                                            .replace(/\[MODE:.*?\]/g, '')
                                            .replace(/Hello! How can I help you today\?/gi, '')
                                            .trim();

                                        if (cleanContent) {
                                            const parsed = parseDownloadContent(cleanContent);

                                            // Main agent content - accumulate it
                                            accumulatedContent += parsed.cleanContent;
                                            if (parsed.download) {
                                                downloadData = parsed.download;
                                                // Download received = response is complete
                                                responseComplete = true;
                                                setIsLoading(false);
                                            }

                                            setCurrentMessages(prev => {
                                                const updated = [...prev];
                                                const lastIdx = updated.length - 1;
                                                if (updated[lastIdx]?.type === 'streaming') {
                                                    updated[lastIdx] = {
                                                        ...updated[lastIdx],
                                                        content: accumulatedContent,
                                                        status: undefined, // Clear status when we have content
                                                        download: downloadData || updated[lastIdx].download,
                                                        type: responseComplete ? undefined : 'streaming' // Finalize if complete
                                                    };
                                                }
                                                return updated;
                                            });
                                        }
                                    }
                                }
                            } else if (data.type === 'done') {
                                // Finalize the message and stop loading
                                responseComplete = true;
                                setIsLoading(false);

                                setCurrentMessages(prev => {
                                    const updated = [...prev];
                                    const lastIdx = updated.length - 1;
                                    if (updated[lastIdx]?.role === 'agent') {
                                        let finalContent = updated[lastIdx].content;

                                        if (!finalContent && downloadData) {
                                            finalContent = 'Report generated successfully! Click below to download.';
                                        } else if (!finalContent) {
                                            finalContent = "I couldn't generate a response.";
                                        }

                                        updated[lastIdx] = {
                                            ...updated[lastIdx],
                                            type: undefined, // Remove streaming type
                                            content: finalContent,
                                            status: undefined,
                                            download: downloadData || updated[lastIdx].download
                                        };
                                    }
                                    return updated;
                                });
                            } else if (data.type === 'error') {
                                throw new Error(data.error);
                            }
                        } catch (parseError) {
                            console.warn('SSE parse error:', parseError, 'Line:', line);
                        }
                    }
                }
            }

            // Refresh threads if new thread was created
            if (!currentThreadId && newThreadId) {
                await refreshThreads();
            }
        } catch (error) {
            console.error('Error sending message:', error);
            setCurrentMessages(prev => {
                // Remove streaming placeholder if exists
                const filtered = prev.filter(m => m.type !== 'streaming');
                return [...filtered, {
                    role: 'agent',
                    content: "Sorry, I encountered an error. Please try again."
                }];
            });
        } finally {
            // Ensure loading is stopped (may already be false if responseComplete)
            if (!responseComplete) {
                setIsLoading(false);
            }
        }
    }, [currentThreadId, isLoading, refreshThreads, deepResearch]);

    const value: ThreadContextType = {
        threads,
        currentThreadId,
        currentMessages,
        isLoading,
        isLoadingThreads,
        deepResearch,
        createThread,
        selectThread,
        deleteThread,
        refreshThreads,
        sendMessage,
        startNewChat,
        setDeepResearch
    };

    return (
        <ThreadContext.Provider value={value}>
            {children}
        </ThreadContext.Provider>
    );
};
