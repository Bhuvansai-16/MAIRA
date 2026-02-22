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

// Research phases for deep search mode
export type ResearchPhase = 'planning' | 'searching' | 'analyzing' | 'reasoning' | 'drafting' | 'finalizing';

export interface PhaseInfo {
    name: string;
    icon: string;
    description: string;
}

export const RESEARCH_PHASES: Record<ResearchPhase, PhaseInfo> = {
    planning: { name: 'Planning', icon: '📋', description: 'Creating research plan' },
    searching: { name: 'Searching', icon: '🔍', description: 'Gathering information' },
    analyzing: { name: 'Analyzing', icon: '📊', description: 'Processing findings' },
    reasoning: { name: 'Reasoning', icon: '🧠', description: 'Deep reasoning & verification' },
    drafting: { name: 'Drafting', icon: '✍️', description: 'Writing content' },
    finalizing: { name: 'Finalizing', icon: '✨', description: 'Completing research' },
};

// Enhanced status event with phase and detail info
export interface StatusEvent {
    type: 'status';
    step: 'start' | 'complete';
    tool: string;
    agent?: string;
    message: string;
    detail?: string;
    phase?: ResearchPhase;
    icon?: string;
    progress?: number;
}

// Phase change event
export interface PhaseEvent {
    type: 'phase';
    phase: ResearchPhase;
    name: string;
    icon: string;
    description: string;
}

// Thinking/reasoning event
export interface ThinkingEvent {
    type: 'thinking';
    content: string;
    phase?: ResearchPhase;
}

// Enhanced init event with mode info
export interface InitEvent {
    type: 'init';
    thread_id: string;
    mode: 'chat' | 'deep_research' | 'literature_survey';
    mode_display: string;
    deep_research: boolean;
    literature_survey: boolean;
    phases?: ResearchPhase[];
}

// Enhanced done event with stats
export interface DoneEvent {
    type: 'done';
    checkpoint_id?: string;
    mode?: string;
    duration_seconds?: number;
    downloads_count?: number;
}

export interface StreamEvent {
    type: 'init' | 'phase' | 'status' | 'thinking' | 'reasoning' | 'text' | 'update' | 'verification' | 'download' | 'done' | 'error' | 'cancelled';
    event_id?: string;
    thread_id?: string;
    checkpoint_id?: string;
    content?: string;
    messages?: AgentMessage[];
    data?: any;
    error?: string;
    // Phase event fields
    phase?: ResearchPhase;
    name?: string;
    icon?: string;
    description?: string;
    // Status event fields
    step?: 'start' | 'complete';
    tool?: string;
    agent?: string;
    message?: string;
    detail?: string;
    progress?: number;
    // Init event fields
    mode?: string;
    mode_display?: string;
    deep_research?: boolean;
    literature_survey?: boolean;
    phases?: ResearchPhase[];
    // Done event fields
    duration_seconds?: number;
    downloads_count?: number;
}
