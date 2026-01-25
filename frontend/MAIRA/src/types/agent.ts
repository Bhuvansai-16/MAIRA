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
