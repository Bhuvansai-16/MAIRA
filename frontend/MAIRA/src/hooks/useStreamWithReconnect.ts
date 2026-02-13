import { useState, useCallback, useRef, useEffect } from 'react';
import type { Message, CheckpointInfo } from '../context/ThreadContextDefinition';

export interface MessageMetadata {
    messageId?: string;
    checkpointId?: string;
    parentCheckpointId?: string;
    timestamp?: string;
    editGroupId?: string;
    versionIndex?: number;
    totalVersions?: number;
}

export interface StreamHookOptions {
    apiBase: string;
    threadId: string | null;
    reconnectOnMount?: boolean;
    onMessageUpdate?: (messages: any[]) => void;
    onStatusUpdate?: (status: string) => void;
    onComplete?: () => void;
    onError?: (error: any) => void;
    user?: any; // User object for auth
}

export interface StreamHookReturn {
    streamMessage: (
        params: {
            prompt: string;
            threadId?: string;
            parentCheckpointId?: string;
            deepResearch?: boolean;
            literatureSurvey?: boolean;
            persona?: string;
        }
    ) => Promise<void>;
    reconnect: (threadId: string) => Promise<void>;
    isLoading: boolean;
    isReconnecting: boolean;
    stopStream: () => void;
    getMessageMetadata: (message: Message, index: number) => MessageMetadata;
}

export const useStreamWithReconnect = (options: StreamHookOptions): StreamHookReturn => {
    const { 
        apiBase, 
        threadId, 
        reconnectOnMount = true, 
        onMessageUpdate, 
        onStatusUpdate, 
        onComplete, 
        onError,
        user
    } = options;

    const [isLoading, setIsLoading] = useState(false);
    const [isReconnecting, setIsReconnecting] = useState(false);
    const abortControllerRef = useRef<AbortController | null>(null);
    const hasCheckedReconnectRef = useRef(false);

    const stopStream = useCallback(() => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
            setIsLoading(false);
            setIsReconnecting(false);
        }
    }, []);

    const processStream = async (response: Response, isReconnect = false) => {
        if (!response.body) throw new Error('No response body');
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let accumulatedContent = '';
        
        // This logic mimics what was in ThreadContext
        try {
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
                            
                            if (data.type === 'ping') continue;
                            
                            // Handle reconnect specific events
                            if (isReconnect && data.type === 'reconnect_complete') {
                                setIsReconnecting(false);
                                onStatusUpdate?.(data.status);
                                if (data.status === 'completed' || data.status === 'error') {
                                    setIsLoading(false);
                                }
                                // Break the loop if we're done catching up and it's completed
                                // Otherwise continue listening if it's still running?
                                // Usually reconnect completes the catchup then standard events follow?
                                // For now let's assume standard events follow or it closes.
                            }

                            if (data.type === 'update' && data.messages) {
                                // Pass messages up
                                onMessageUpdate?.(data.messages);
                            }
                            
                            // Logic for status updates...
                            if (data.status) {
                                onStatusUpdate?.(data.status);
                            }

                            // Handle error
                            if (data.type === 'error') {
                                throw new Error(data.error || 'Stream error');
                            }
                            
                            // Handle done
                            if (data.type === 'done') {
                                setIsLoading(false);
                            }

                        } catch (e) {
                            console.warn('Error parsing SSE:', e);
                        }
                    }
                }
            }
        } catch (error) {
            if ((error as Error).name !== 'AbortError') {
                throw error;
            }
        } finally {
            reader.releaseLock();
            if (!isReconnect) setIsLoading(false);
            onComplete?.();
        }
    };

    const streamMessage = useCallback(async (params: {
        prompt: string;
        threadId?: string;
        parentCheckpointId?: string;
        deepResearch?: boolean;
        literatureSurvey?: boolean;
        persona?: string;
    }) => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();
        setIsLoading(true);

        try {
            const body = {
                prompt: params.prompt,
                thread_id: params.threadId,
                user_id: user?.id,
                deep_research: params.deepResearch,
                literature_survey: params.literatureSurvey,
                persona: params.persona,
                parent_checkpoint_id: params.parentCheckpointId
            };

            const response = await fetch(`${apiBase}/run-agent`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal: abortControllerRef.current.signal
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            await processStream(response, false);

        } catch (error) {
            setIsLoading(false);
            onError?.(error);
        }
    }, [apiBase, user, onError]);

    const reconnect = useCallback(async (tid: string) => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();
        setIsReconnecting(true);
        setIsLoading(true);

        try {
            const response = await fetch(`${apiBase}/sessions/${tid}/stream?from_index=0`, {
                signal: abortControllerRef.current.signal
            });
            
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            
            await processStream(response, true);
        } catch (error) {
            setIsLoading(false);
            setIsReconnecting(false);
            onError?.(error);
        }
    }, [apiBase, onError]);

    // Reconnect on mount if enabled and threadId exists
    useEffect(() => {
        if (reconnectOnMount && threadId && !hasCheckedReconnectRef.current && user?.id) {
            hasCheckedReconnectRef.current = true;
            // Check if there is an active run before reconnecting?
            // Or just try reconnecting. Usually good to check status first.
            // For now, we expose 'reconnect' function and let consumer decide logic or do it here.
            // Let's do a status check first if possible, or just call reconnect.
            // But ThreadContext usually handles the "check status then reconnect" logic.
            // Keep this hook simple: Provide the primitives.
        }
    }, [reconnectOnMount, threadId, user]);

    // Calculate metadata for branching
    const getMessageMetadata = useCallback((message: Message, index: number): MessageMetadata => {
        // Find the checkpoint ID for this message
        // Usually attached to the message object or derived
        
        let checkpointId = message.checkpoint_id;
        
        // If not explicit, might need to look at versions
        // Simplified logic:
        return {
            messageId: message.message_id,
            checkpointId: checkpointId,
            parentCheckpointId: message.checkpoint_id, // For now assuming checkpoint_id points to state AFTER this message
            editGroupId: message.editGroupId,
            versionIndex: message.currentVersionIndex,
            totalVersions: message.versions?.length || 1
        };
    }, []);

    return {
        streamMessage,
        reconnect,
        isLoading,
        isReconnecting,
        stopStream,
        getMessageMetadata
    };
};
