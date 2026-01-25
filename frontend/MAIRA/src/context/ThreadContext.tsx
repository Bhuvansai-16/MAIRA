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
    type?: string;
}

interface ThreadContextType {
    threads: Thread[];
    currentThreadId: string | null;
    currentMessages: Message[];
    isLoading: boolean;
    isLoadingThreads: boolean;
    // Actions
    createThread: (title?: string) => Promise<Thread>;
    selectThread: (threadId: string) => Promise<void>;
    deleteThread: (threadId: string) => Promise<void>;
    refreshThreads: () => Promise<void>;
    sendMessage: (prompt: string) => Promise<void>;
    startNewChat: () => void;
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

                // Skip tool messages
                if (isTool) return null;

                let content = '';
                if (typeof msg.content === 'string') {
                    content = msg.content;
                } else if (Array.isArray(msg.content)) {
                    content = msg.content
                        .map((c: any) => typeof c === 'string' ? c : (c.text || ''))
                        .join('');
                }

                if (!content.trim()) return null;

                return {
                    role: isUser ? 'user' : 'agent',
                    content: content
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

    // Send a message
    const sendMessage = useCallback(async (prompt: string) => {
        if (!prompt.trim() || isLoading) return;

        // Add user message immediately
        setCurrentMessages(prev => [...prev, { role: 'user', content: prompt }]);
        setIsLoading(true);

        try {
            const response = await axios.post(`${API_BASE}/run-agent`, {
                prompt,
                thread_id: currentThreadId
            });

            const result = response.data;
            const newThreadId = result.thread_id;

            // Update current thread ID if it's a new thread
            if (!currentThreadId && newThreadId) {
                setCurrentThreadId(newThreadId);
                // Refresh threads to show the new one
                await refreshThreads();
            }

            // Extract agent response
            let agentResponseContent = "I couldn't generate a response.";
            const output = result.output !== undefined ? result.output : result;

            if (Array.isArray(output)) {
                for (let i = output.length - 1; i >= 0; i--) {
                    const msg = output[i];

                    let content = '';
                    if (typeof msg.content === 'string') {
                        content = msg.content;
                    } else if (Array.isArray(msg.content)) {
                        content = msg.content
                            .map((c: any) => typeof c === 'string' ? c : (c.text || ''))
                            .join('');
                    }

                    if (content.trim().length > 0) {
                        const isHuman = msg.type === 'human' || msg.role === 'user';
                        const isTool = msg.type === 'tool' || msg.type === 'tool_call' || msg.role === 'tool';

                        if (!isHuman && !isTool) {
                            agentResponseContent = content;
                            break;
                        }
                    }
                }
            } else if (typeof output === 'string') {
                agentResponseContent = output;
            } else if (output && typeof output === 'object') {
                agentResponseContent = output.content || output.text || JSON.stringify(output);
            }

            setCurrentMessages(prev => [...prev, { role: 'agent', content: agentResponseContent }]);
        } catch (error) {
            console.error('Error sending message:', error);
            setCurrentMessages(prev => [...prev, {
                role: 'agent',
                content: "Sorry, I encountered an error. Please try again."
            }]);
        } finally {
            setIsLoading(false);
        }
    }, [currentThreadId, isLoading, refreshThreads]);

    const value: ThreadContextType = {
        threads,
        currentThreadId,
        currentMessages,
        isLoading,
        isLoadingThreads,
        createThread,
        selectThread,
        deleteThread,
        refreshThreads,
        sendMessage,
        startNewChat
    };

    return (
        <ThreadContext.Provider value={value}>
            {children}
        </ThreadContext.Provider>
    );
};
