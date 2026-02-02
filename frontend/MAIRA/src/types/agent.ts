export interface ToolCall {
    name: string;
    args: Record<string, any>;
    id: string;
    type: 'tool_call';
}

export interface AgentMessage {
    type: 'human' | 'ai' | 'tool' | 'system';
    content: string;
    tool_calls?: ToolCall[];
    id?: string;
    name?: string;
    additional_kwargs?: Record<string, any>;
    response_metadata?: Record<string, any>;
}

export interface AgentResponse {
    output: AgentMessage[]; // The backend returns an array of messages
}

// Verification Types - Production Quality Indicators
export type VerificationStatusType = 'VALID' | 'NEEDS_REVISION' | 'INVALID' | 'PENDING' | 'VERIFYING';

export interface CitationResult {
    url: string;
    valid: boolean;
    status_code?: number;
    error?: string;
}

export interface FactCheckResult {
    claim: string;
    verified: boolean;
    confidence: number;
    sources?: string[];
    explanation?: string;
}

export interface VerificationData {
    overallScore: number;
    status: VerificationStatusType;
    citationScore?: number;
    factCheckScore?: number;
    qualityScore?: number;
    completenessScore?: number;
    validCitations?: number;
    totalCitations?: number;
    verifiedFacts?: number;
    totalFacts?: number;
    citationResults?: CitationResult[];
    factCheckResults?: FactCheckResult[];
    issues?: string[];
    timestamp?: string;
    reflectionLoop?: {
        iteration: number;
        maxIterations: number;
        previousScore?: number;
        improved: boolean;
    };
}

export interface VerificationUpdate {
    type: 'verification';
    stage: 'citations' | 'facts' | 'quality' | 'completeness' | 'final';
    data: Partial<VerificationData>;
}

export interface ResearchProgress {
    currentAgent: string;
    currentTask: string;
    progress: number; // 0-100
    verification?: VerificationData;
}

// Time Travel & Branching Types
export interface CheckpointInfo {
    checkpoint_id: string;
    thread_id: string;
    timestamp: string;
    message_count: number;
    parent_checkpoint_id?: string;
    metadata?: {
        description?: string;
        is_branch_point?: boolean;
    };
}

export interface Branch {
    branch_id: string;
    parent_thread_id: string;
    fork_checkpoint_id: string;
    created_at: string;
    title?: string;
}

// Content Block Types for Reasoning Streams
export type ContentBlockType = 'text' | 'reasoning' | 'tool_use' | 'tool_result';

export interface ContentBlock {
    type: ContentBlockType;
    content: string;
    metadata?: Record<string, any>;
}

export interface StreamEvent {
    type: 'init' | 'reasoning' | 'text' | 'update' | 'verification' | 'done' | 'error';
    event_id?: string;
    thread_id?: string;
    checkpoint_id?: string;
    content?: string;
    messages?: AgentMessage[];
    data?: any;
    error?: string;
}
