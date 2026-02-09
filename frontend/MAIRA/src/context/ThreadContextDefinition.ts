import { createContext } from 'react';
import type { VerificationData, CheckpointInfo } from '../types/agent';

export interface Thread {
    thread_id: string;
    title: string;
    created_at: string;
    updated_at: string;
    parent_thread_id?: string;
    fork_checkpoint_id?: string;
}

// A single version of a message pair (user question + agent response)
export interface MessageVersion {
    userContent: string;
    agentContent?: string;
    agentReasoning?: string;
    agentDownload?: {
        filename: string;
        data: string;
    };
    agentVerification?: import('../types/agent').VerificationData;
    timestamp: string;
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
    attachments?: { name: string; type: 'file' | 'image' }[];  // Uploaded file references
    download?: {
        filename: string;
        data: string;  // Base64 encoded
    };
    verification?: VerificationData;
    // Version tracking for editable messages
    versions?: MessageVersion[];  // All versions of this message pair
    currentVersionIndex?: number;  // Currently displayed version (0-based)
    editGroupId?: string;  // Links user message to its agent response
}

export interface ActiveStep {
    tool: string;
    message: string;
    status: 'loading' | 'done';
    timestamp: number;
}

export interface BackendMessage {
    type?: string;
    role?: string;
    content: string | Array<{ type: string; text?: string; [key: string]: unknown }>;
    tool_calls?: Array<{ name: string; [key: string]: unknown }>;
    [key: string]: unknown;
}

export type ResearchMode = 'chat' | 'deep_research' | 'literature_survey';

export interface ThreadContextType {
    threads: Thread[];
    currentThreadId: string | null;
    currentMessages: Message[];
    checkpoints: CheckpointInfo[];
    isLoading: boolean;
    isLoadingThreads: boolean;
    deepResearch: boolean;
    literatureSurvey: boolean;
    persona: string;
    lastEventId: string | null;
    activeSteps: Record<string, ActiveStep>;  // Track active tool/subagent steps
    showThinking: boolean;  // Toggle thinking/reasoning display
    // Actions
    createThread: (title?: string) => Promise<Thread>;
    selectThread: (threadId: string) => Promise<void>;
    deleteThread: (threadId: string) => Promise<void>;
    refreshThreads: () => Promise<void>;
    sendMessage: (prompt: string, parentCheckpointId?: string, attachments?: { name: string; type: 'file' | 'image' }[]) => Promise<void>;
    editMessage: (messageIndex: number, newContent: string) => Promise<void>;
    setMessageVersion: (messageIndex: number, versionIndex: number) => void;  // Navigate between versions
    startNewChat: () => void;
    setDeepResearch: (enabled: boolean) => void;
    setLiteratureSurvey: (enabled: boolean) => void;
    setPersona: (persona: string) => void;
    setShowThinking: (show: boolean) => void;
    fetchStateHistory: (threadId: string) => Promise<CheckpointInfo[]>;
    branchFromCheckpoint: (checkpointId: string) => Promise<Thread | null>;
    stopStream: () => void;
    // Uploads
    uploadFile: (file: File) => Promise<void>;
    uploadImage: (file: File, description?: string) => Promise<void>;
}

export const ThreadContext = createContext<ThreadContextType | null>(null);
