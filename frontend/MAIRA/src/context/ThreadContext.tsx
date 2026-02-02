import { createContext, useContext, useState, useCallback, useEffect, useRef, useMemo } from 'react';
import type { ReactNode } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import type { VerificationData, VerificationStatusType, CheckpointInfo } from '../types/agent';

const API_BASE = 'http://localhost:8000';

// Types
export interface Thread {
    thread_id: string;
    title: string;
    created_at: string;
    updated_at: string;
    parent_thread_id?: string;
    fork_checkpoint_id?: string;
}

export interface Message {
    role: 'user' | 'agent';
    content: string;
    thought?: string;
    reasoning?: string;  // For reasoning/thinking blocks
    status?: string;
    type?: 'streaming' | 'final';
    message_id?: string;  // For editing messages
    checkpoint_id?: string;  // For time travel
    download?: {
        filename: string;
        data: string;  // Base64 encoded
    };
    verification?: VerificationData;
}

// Active step status for real-time progress display
export interface ActiveStep {
    tool: string;
    message: string;
    status: 'loading' | 'done';
    timestamp: number;
}

interface ThreadContextType {
    threads: Thread[];
    currentThreadId: string | null;
    currentMessages: Message[];
    checkpoints: CheckpointInfo[];
    isLoading: boolean;
    isLoadingThreads: boolean;
    deepResearch: boolean;
    lastEventId: string | null;
    activeSteps: Record<string, ActiveStep>;  // Track active tool/subagent steps
    // Actions
    createThread: (title?: string) => Promise<Thread>;
    selectThread: (threadId: string) => Promise<void>;
    deleteThread: (threadId: string) => Promise<void>;
    refreshThreads: () => Promise<void>;
    sendMessage: (prompt: string, parentCheckpointId?: string) => Promise<void>;
    editMessage: (messageIndex: number, newContent: string) => Promise<void>;
    startNewChat: () => void;
    setDeepResearch: (enabled: boolean) => void;
    fetchStateHistory: (threadId: string) => Promise<CheckpointInfo[]>;
    branchFromCheckpoint: (checkpointId: string) => Promise<Thread | null>;
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
    const { threadId: urlThreadId } = useParams<{ threadId?: string }>();
    const navigate = useNavigate();
    
    const [threads, setThreads] = useState<Thread[]>([]);
    const [currentThreadId, setCurrentThreadId] = useState<string | null>(() => {
        // Restore thread ID from localStorage on mount
        return localStorage.getItem('maira_current_thread_id');
    });
    const [currentMessages, setCurrentMessages] = useState<Message[]>([
        { role: 'agent', content: "Hello! I am MAIRA, your advanced research agent. How can I help you today?" }
    ]);
    const [checkpoints, setCheckpoints] = useState<CheckpointInfo[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingThreads, setIsLoadingThreads] = useState(false);
    const [deepResearch, setDeepResearch] = useState(false);
    const [lastEventId, setLastEventId] = useState<string | null>(null);
    const [isReconnecting, setIsReconnecting] = useState(false);
    const [activeSteps, setActiveSteps] = useState<Record<string, ActiveStep>>({});
    
    // Reconnection state
    const reconnectAttempts = useRef(0);
    const maxReconnectAttempts = 3;
    const abortControllerRef = useRef<AbortController | null>(null);

    // Persist current thread ID to localStorage
    useEffect(() => {
        if (currentThreadId) {
            localStorage.setItem('maira_current_thread_id', currentThreadId);
        } else {
            localStorage.removeItem('maira_current_thread_id');
        }
    }, [currentThreadId]);

    // Check for active session and reconnect on mount
    useEffect(() => {
        const checkAndReconnect = async () => {
            const savedThreadId = localStorage.getItem('maira_current_thread_id');
            if (!savedThreadId) return;

            try {
                // Check if there's an active session
                const response = await axios.get(`${API_BASE}/sessions/${savedThreadId}/status`);
                const sessionStatus = response.data;

                if (sessionStatus.has_active_stream || sessionStatus.status === 'running') {
                    console.log('Found active session, reconnecting...', sessionStatus);
                    setIsReconnecting(true);
                    setIsLoading(true);
                    setCurrentThreadId(savedThreadId);

                    // Load existing messages first
                    try {
                        const messagesResponse = await axios.get(`${API_BASE}/threads/${savedThreadId}/messages`);
                        const messages = messagesResponse.data.messages || [];
                        const formattedMessages = formatMessagesFromBackend(messages);
                        
                        // Add user message that triggered the stream if available
                        if (sessionStatus.prompt) {
                            const hasUserMessage = formattedMessages.some(
                                (m: Message) => m.role === 'user' && m.content === sessionStatus.prompt
                            );
                            if (!hasUserMessage) {
                                formattedMessages.push({ role: 'user', content: sessionStatus.prompt });
                            }
                        }
                        
                        // Add streaming placeholder
                        formattedMessages.push({
                            role: 'agent',
                            content: sessionStatus.last_content || '',
                            status: 'Reconnecting...',
                            type: 'streaming'
                        });
                        
                        setCurrentMessages(formattedMessages);
                    } catch (e) {
                        console.warn('Failed to load existing messages:', e);
                    }

                    // Reconnect to the event stream
                    await reconnectToStream(savedThreadId);
                } else if (sessionStatus.status === 'completed' || sessionStatus.status === 'none') {
                    // Session completed or doesn't exist, just load messages normally
                    if (savedThreadId) {
                        selectThread(savedThreadId);
                    }
                }
            } catch (error) {
                console.error('Failed to check session status:', error);
                // Fall back to loading thread normally
                if (savedThreadId) {
                    selectThread(savedThreadId);
                }
            }
        };

        checkAndReconnect();
    }, []); // Only run on mount

    // Helper function to format messages from backend
    const formatMessagesFromBackend = (messages: any[]): Message[] => {
        const formattedMessages: Message[] = messages.map((msg: any) => {
            const isUser = msg.type === 'human' || msg.role === 'user';
            const isTool = msg.type === 'tool' || msg.role === 'tool';

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
        }).reduce((acc: Message[], msg) => {
            // Filter nulls
            if (!msg) return acc;
            
            // Handle merging of consecutive agent messages for downloads
            if (msg.role === 'agent') {
                const prevMsg = acc[acc.length - 1];
                
                // Case 1: Current message has download, previous message looks like its content
                if (msg.download && prevMsg && prevMsg.role === 'agent') {
                    // Merge download into previous message
                    prevMsg.download = msg.download;
                    
                    // If current message has actual content other than default
                    if (msg.content !== 'Report generated successfully! Click below to download.') {
                         prevMsg.content = `${prevMsg.content}\n\n${msg.content}`;
                    }
                    return acc;
                }
                
                // Case 2: Current message is content, previous message was just a download placeholder
                if (prevMsg && prevMsg.role === 'agent' && prevMsg.download) {
                     if (prevMsg.content === 'Report generated successfully! Click below to download.') {
                         // Replace placeholder with real content
                         prevMsg.content = msg.content;
                         return acc;
                     }
                     // Or append it
                     prevMsg.content = `${prevMsg.content}\n\n${msg.content}`;
                     return acc;
                }
            }
            
            acc.push(msg);
            return acc;
        }, []);

        if (formattedMessages.length === 0) {
            formattedMessages.push({
                role: 'agent',
                content: "Hello! I am MAIRA, your advanced research agent. How can I help you today?"
            });
        }

        return formattedMessages;
    };

    // Reconnect to an active stream
    const reconnectToStream = async (threadId: string) => {
        try {
            const response = await fetch(`${API_BASE}/sessions/${threadId}/stream?from_index=0`);
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let accumulatedContent = '';

            if (!reader) {
                throw new Error('No response body reader available');
            }

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const text = decoder.decode(value, { stream: true });
                buffer += text;

                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            console.log('Reconnect SSE data:', data);
                            
                            // Skip ping events
                            if (data.type === 'ping') continue;

                            if (data.type === 'reconnect_complete') {
                                setIsReconnecting(false);
                                if (data.status === 'completed' || data.status === 'error') {
                                    setIsLoading(false);
                                    // Finalize the message
                                    setCurrentMessages(prev => {
                                        const updated = [...prev];
                                        const lastIdx = updated.length - 1;
                                        if (updated[lastIdx]?.type === 'streaming') {
                                            updated[lastIdx] = {
                                                ...updated[lastIdx],
                                                type: undefined,
                                                status: undefined
                                            };
                                        }
                                        return updated;
                                    });
                                }
                                break;
                            }

                            if (data.type === 'update' && data.messages) {
                                for (const msg of data.messages) {
                                    if (msg.content && msg.type !== 'human') {
                                        accumulatedContent += msg.content;
                                        setCurrentMessages(prev => {
                                            const updated = [...prev];
                                            const lastIdx = updated.length - 1;
                                            if (updated[lastIdx]?.type === 'streaming') {
                                                updated[lastIdx] = {
                                                    ...updated[lastIdx],
                                                    content: accumulatedContent,
                                                    status: data.replayed ? 'Catching up...' : undefined
                                                };
                                            }
                                            return updated;
                                        });
                                    }
                                }
                            } else if (data.type === 'done') {
                                setIsLoading(false);
                                setIsReconnecting(false);
                                setCurrentMessages(prev => {
                                    const updated = [...prev];
                                    const lastIdx = updated.length - 1;
                                    if (updated[lastIdx]?.type === 'streaming') {
                                        updated[lastIdx] = {
                                            ...updated[lastIdx],
                                            type: undefined,
                                            status: undefined,
                                            content: accumulatedContent || updated[lastIdx].content || "Response completed."
                                        };
                                    }
                                    return updated;
                                });
                            }
                        } catch (parseError) {
                            console.warn('Reconnect SSE parse error:', parseError);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Failed to reconnect to stream:', error);
            setIsReconnecting(false);
            setIsLoading(false);
            // Load messages normally as fallback
            selectThread(threadId);
        }
    };

    // Sync URL with currentThreadId
    useEffect(() => {
        if (currentThreadId && currentThreadId !== urlThreadId) {
            navigate(`/chat/${currentThreadId}`, { replace: true });
        } else if (!currentThreadId && urlThreadId) {
            navigate('/chat', { replace: true });
        }
    }, [currentThreadId, urlThreadId, navigate]);

    // Load thread from URL on mount (reconnectOnMount behavior)
    useEffect(() => {
        if (urlThreadId && urlThreadId !== currentThreadId && !isReconnecting) {
            selectThread(urlThreadId);
        }
    }, [urlThreadId, isReconnecting]);

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

    // Fetch state history for time travel
    const fetchStateHistory = useCallback(async (threadId: string): Promise<CheckpointInfo[]> => {
        try {
            const response = await axios.get(`${API_BASE}/threads/${threadId}/history`);
            const history = response.data.checkpoints || [];
            setCheckpoints(history);
            return history;
        } catch (error) {
            console.error('Failed to fetch state history:', error);
            return [];
        }
    }, []);

    // Branch from a specific checkpoint
    const branchFromCheckpoint = useCallback(async (checkpointId: string): Promise<Thread | null> => {
        if (!currentThreadId) return null;
        try {
            const response = await axios.post(`${API_BASE}/threads/${currentThreadId}/branch`, {
                checkpoint_id: checkpointId
            });
            const newThread = response.data;
            setThreads(prev => [newThread, ...prev]);
            await selectThread(newThread.thread_id);
            return newThread;
        } catch (error) {
            console.error('Failed to branch from checkpoint:', error);
            return null;
        }
    }, [currentThreadId]);

    // Select a thread and load its messages
    const selectThread = useCallback(async (threadId: string) => {
        setCurrentThreadId(threadId);
        setIsLoading(true);

        try {
            const response = await axios.get(`${API_BASE}/threads/${threadId}/messages`);
            const messages = response.data.messages || [];
            const formattedMessages = formatMessagesFromBackend(messages);
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
    const sendMessage = useCallback(async (prompt: string, parentCheckpointId?: string) => {
        if (!prompt.trim() || isLoading) return;

        // Cancel any existing request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        // Add user message immediately
        setCurrentMessages(prev => [...prev, { role: 'user', content: prompt }]);
        setIsLoading(true);

        let newThreadId = currentThreadId;
        let accumulatedContent = '';
        let accumulatedReasoning = '';
        let buffer = ''; // Buffer for incomplete SSE lines
        let downloadData: { filename: string; data: string } | undefined = undefined;
        let verificationData: VerificationData | undefined = undefined;
        let responseComplete = false; // Track when we have a complete response
        let currentEventId: string | null = null;

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

        // Helper to parse verification markers from content
        const parseVerificationContent = (content: string): { cleanContent: string; verification?: VerificationData } => {
            const verificationMarker = '[VERIFICATION]';
            
            if (content.includes(verificationMarker)) {
                const index = content.indexOf(verificationMarker);
                
                try {
                    const jsonPart = content.substring(index + verificationMarker.length).trim();
                    const lastBrace = jsonPart.lastIndexOf('}');
                    
                    if (lastBrace !== -1) {
                        const jsonStr = jsonPart.substring(0, lastBrace + 1);
                        const verification = JSON.parse(jsonStr) as VerificationData;
                        const cleanContent = content.substring(0, index).trim();
                        console.log("Verification parsed:", verification.status, verification.overallScore);
                        return { cleanContent, verification };
                    }
                } catch (e) {
                    console.warn('Failed to parse verification data JSON:', e);
                }
            }
            
            return { cleanContent: content };
        };

        // Helper to parse reasoning/thinking blocks from content
        const parseReasoningContent = (content: string): { cleanContent: string; reasoning?: string } => {
            const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/);
            if (thinkMatch) {
                const reasoning = thinkMatch[1].trim();
                const cleanContent = content.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
                return { cleanContent, reasoning };
            }
            return { cleanContent: content };
        };

        // Helper to determine verification status from tool calls
        const getVerificationStatus = (toolNames: string[]): string => {
            const verificationTools = ['validate_citations', 'fact_check_claims', 'assess_content_quality', 'cross_reference_sources', 'verify_draft_completeness'];
            const activeVerification = toolNames.find(name => verificationTools.includes(name));
            
            if (activeVerification) {
                switch (activeVerification) {
                    case 'validate_citations': return '🔗 Validating citations...';
                    case 'fact_check_claims': return '✓ Fact-checking claims...';
                    case 'assess_content_quality': return '📊 Assessing quality...';
                    case 'cross_reference_sources': return '🔄 Cross-referencing sources...';
                    case 'verify_draft_completeness': return '📝 Verifying completeness...';
                    default: return `🔍 ${activeVerification}`;
                }
            }
            return `🔍 Researching... (${toolNames.join(', ')})`;
        };

        // Reconnection logic
        const connectStream = async (retryCount = 0): Promise<void> => {
            try {
                const requestBody: any = { 
                    prompt, 
                    thread_id: currentThreadId, 
                    deep_research: deepResearch 
                };
                
                // For branching: include parent checkpoint ID
                if (parentCheckpointId) {
                    requestBody.parent_checkpoint_id = parentCheckpointId;
                }
                
                // For reconnection: include last event ID
                if (lastEventId && retryCount > 0) {
                    requestBody.last_event_id = lastEventId;
                }

                const response = await fetch(`${API_BASE}/run-agent`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody),
                    signal: abortControllerRef.current?.signal
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
                if (retryCount === 0) {
                    setCurrentMessages(prev => [...prev, { role: 'agent', content: '', status: 'Thinking...', type: 'streaming' }]);
                }

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
                                
                                // Skip ping events (keepalive)
                                if (data.type === 'ping') continue;
                                
                                // Track event ID for reconnection
                                if (data.event_id) {
                                    currentEventId = data.event_id;
                                    setLastEventId(data.event_id);
                                }
                                
                                // Handle already_running status (session reconnect)
                                if (data.status === 'already_running') {
                                    console.log('Session already running, subscribing to existing stream');
                                    // The backend will stream from the existing task
                                    continue;
                                }

                                if (data.type === 'init' && data.thread_id) {
                                    newThreadId = data.thread_id;
                                    if (!currentThreadId) {
                                        setCurrentThreadId(newThreadId);
                                    }
                                    // Clear active steps on new conversation
                                    setActiveSteps({});
                                } else if (data.type === 'status') {
                                    // Handle real-time status updates for tools/subagents
                                    const { tool, step, message } = data;
                                    if (tool) {
                                        setActiveSteps(prev => ({
                                            ...prev,
                                            [tool]: {
                                                tool,
                                                message: message || tool,
                                                status: step === 'start' ? 'loading' : 'done',
                                                timestamp: Date.now()
                                            }
                                        }));
                                        
                                        // Update streaming message status with current tool
                                        if (step === 'start') {
                                            setCurrentMessages(prev => {
                                                const updated = [...prev];
                                                const lastIdx = updated.length - 1;
                                                if (updated[lastIdx]?.type === 'streaming') {
                                                    updated[lastIdx] = {
                                                        ...updated[lastIdx],
                                                        status: message || `Running ${tool}...`
                                                    };
                                                }
                                                return updated;
                                            });
                                        }
                                    }
                                } else if (data.type === 'reasoning') {
                                    // Handle reasoning/thinking blocks separately
                                    const reasoningText = data.content || '';
                                    accumulatedReasoning += reasoningText;
                                    
                                    setCurrentMessages(prev => {
                                        const updated = [...prev];
                                        const lastIdx = updated.length - 1;
                                        if (updated[lastIdx]?.type === 'streaming') {
                                            updated[lastIdx] = {
                                                ...updated[lastIdx],
                                                reasoning: accumulatedReasoning,
                                                status: '💭 Thinking...'
                                            };
                                        }
                                        return updated;
                                    });
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
                                        const toolNames = msg.tool_calls.map((tc: any) => tc.name);
                                        const status = getVerificationStatus(toolNames);

                                        // Check if this is a verification tool - set verifying status
                                        const verificationTools = ['validate_citations', 'fact_check_claims', 'assess_content_quality', 'cross_reference_sources', 'verify_draft_completeness'];
                                        const isVerifying = toolNames.some((name: string) => verificationTools.includes(name));

                                        setCurrentMessages(prev => {
                                            const updated = [...prev];
                                            const lastIdx = updated.length - 1;
                                            if (updated[lastIdx]?.type === 'streaming') {
                                                updated[lastIdx] = { 
                                                    ...updated[lastIdx], 
                                                    status,
                                                    verification: isVerifying ? {
                                                        ...updated[lastIdx].verification,
                                                        status: 'VERIFYING',
                                                        overallScore: 0,
                                                        timestamp: new Date().toISOString()
                                                    } : updated[lastIdx].verification
                                                };
                                            }
                                            return updated;
                                        });
                                    }
                                    else if (msg.content && msg.type !== 'human') {
                                        const textContent = extractContent(msg.content);
                                        let cleanContent = textContent
                                            .replace(/\[MODE:.*?\]/g, '')
                                            .trim();

                                        if (cleanContent) {
                                            // Parse verification data first
                                            const verificationParsed = parseVerificationContent(cleanContent);
                                            cleanContent = verificationParsed.cleanContent;
                                            if (verificationParsed.verification) {
                                                verificationData = verificationParsed.verification;
                                            }

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
                                                        verification: verificationData || updated[lastIdx].verification,
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
                                
                                // Clear active steps when done
                                setActiveSteps({});

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
                                            download: downloadData || updated[lastIdx].download,
                                            verification: verificationData || updated[lastIdx].verification
                                        };
                                    }
                                    return updated;
                                });
                            } else if (data.type === 'verification' && data.data) {
                                // Handle verification updates
                                verificationData = {
                                    ...verificationData,
                                    ...data.data,
                                    timestamp: new Date().toISOString()
                                } as VerificationData;
                                
                                setCurrentMessages(prev => {
                                    const updated = [...prev];
                                    const lastIdx = updated.length - 1;
                                    if (updated[lastIdx]?.type === 'streaming') {
                                        updated[lastIdx] = {
                                            ...updated[lastIdx],
                                            verification: verificationData
                                        };
                                    }
                                    return updated;
                                });
                            } else if (data.type === 'error') {
                                // Handle error event from backend
                                console.error('Agent error:', data.error);
                                responseComplete = true;
                                setIsLoading(false);
                                
                                setCurrentMessages(prev => {
                                    const updated = [...prev];
                                    const lastIdx = updated.length - 1;
                                    if (updated[lastIdx]?.type === 'streaming') {
                                        // Replace streaming message with error message
                                        updated[lastIdx] = {
                                            role: 'agent',
                                            content: `⚠️ An error occurred: ${data.error}\n\nPlease try again or rephrase your request.`,
                                            type: undefined,
                                            status: undefined
                                        };
                                    }
                                    return updated;
                                });
                                
                                // Stop processing further events
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
                
                // Reset reconnect attempts on success
                reconnectAttempts.current = 0;
                
            } catch (error: any) {
                // Check if error is due to abort (user cancelled)
                if (error.name === 'AbortError') {
                    console.log('Request aborted by user');
                    setIsLoading(false);
                    return;
                }
                
                // Attempt reconnection only for network errors, not agent errors
                const isAgentError = error.message && error.message.includes('Agent error');
                if (!isAgentError && retryCount < maxReconnectAttempts && !responseComplete) {
                    console.log(`Connection lost, attempting reconnect (${retryCount + 1}/${maxReconnectAttempts})...`);
                    reconnectAttempts.current = retryCount + 1;
                    await new Promise(resolve => setTimeout(resolve, 1000 * (retryCount + 1))); // Exponential backoff
                    return connectStream(retryCount + 1);
                }
                
                console.error('Error sending message:', error);
                setIsLoading(false);  // Ensure loading is stopped
                setCurrentMessages(prev => {
                    // Remove streaming placeholder if exists
                    const filtered = prev.filter(m => m.type !== 'streaming');
                    return [...filtered, {
                        role: 'agent',
                        content: `⚠️ ${isAgentError ? 'Agent error' : 'Connection error'}: ${error.message || 'Please try again.'}`
                    }];
                });
            } finally {
                // Ensure loading is stopped
                if (responseComplete) {
                    setIsLoading(false);
                }
                abortControllerRef.current = null;
            }
                if (!responseComplete) {
                    setIsLoading(false);
                }
        };

        // Start the stream connection
        await connectStream();

    }, [currentThreadId, isLoading, refreshThreads, deepResearch, lastEventId]);

    // Edit a message and trigger regeneration from that point (branching)
    const editMessage = useCallback(async (messageIndex: number, newContent: string) => {
        if (isLoading) return;
        
        // Get the message to edit
        const messageToEdit = currentMessages[messageIndex];
        if (!messageToEdit || messageToEdit.role !== 'user') return;
        
        // Get checkpoint ID from the message before the edited one (if available)
        const previousMessage = messageIndex > 0 ? currentMessages[messageIndex - 1] : null;
        const parentCheckpointId = previousMessage?.checkpoint_id;
        
        // Truncate messages to the point of edit
        setCurrentMessages(prev => prev.slice(0, messageIndex));
        
        // Send the edited message with parent checkpoint for branching
        await sendMessage(newContent, parentCheckpointId);
    }, [currentMessages, isLoading, sendMessage]);

    const value = useMemo<ThreadContextType>(() => ({
        threads,
        currentThreadId,
        currentMessages,
        checkpoints,
        isLoading,
        isLoadingThreads,
        deepResearch,
        lastEventId,
        activeSteps,
        createThread,
        selectThread,
        deleteThread,
        refreshThreads,
        sendMessage,
        editMessage,
        startNewChat,
        setDeepResearch,
        fetchStateHistory,
        branchFromCheckpoint
    }), [
        threads,
        currentThreadId,
        currentMessages,
        checkpoints,
        isLoading,
        isLoadingThreads,
        deepResearch,
        lastEventId,
        activeSteps,
        createThread,
        selectThread,
        deleteThread,
        refreshThreads,
        sendMessage,
        editMessage,
        startNewChat,
        setDeepResearch,
        fetchStateHistory,
        branchFromCheckpoint
    ]);

    return (
        <ThreadContext.Provider value={value}>
            {children}
        </ThreadContext.Provider>
    );
};
