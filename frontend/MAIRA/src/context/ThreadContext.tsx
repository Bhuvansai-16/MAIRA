import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import type { ReactNode } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import type { VerificationData, CheckpointInfo } from '../types/agent';
import type { BackendMessage } from './ThreadContextDefinition';
import { ThreadContext } from './ThreadContextDefinition';
import type { Thread, Message, ActiveStep, ThreadContextType, MessageVersion, MessageMetadata, CustomPersona } from './ThreadContextDefinition';
import { useAuth } from './AuthContext';
import { toast } from 'sonner';
import { API_BASE } from '../lib/config';

// Re-export types for consumers
export type { Thread, Message, ActiveStep, ThreadContextType, MessageVersion, MessageMetadata, CustomPersona };

// Maps backend tool/agent names to the ResearchPhase keys expected by DeepResearchProgress
const getPhaseFromToolName = (toolName: string): string => {
    const name = toolName.toLowerCase();

    if (name.includes('websearch') || name.includes('internet_search') || name.includes('search') || name.includes('arxiv')) {
        return 'searching';
    } else if (name.includes('draft')) {
        return 'drafting';
    } else if (name.includes('reasoning') || name.includes('fact_check') || name.includes('verify') || name.includes('validate')) {
        return 'reasoning';
    } else if (name.includes('report') || name.includes('export') || name.includes('pdf') || name.includes('docx') || name.includes('finalize') || name.includes('summary')) {
        return 'finalizing';
    }

    return 'searching'; // Default to searching if we are running tools
};

// Helper to calculate a rough progress percentage based on phase
const getProgressFromPhase = (phase: string): number => {
    const phases = ['planning', 'searching', 'drafting', 'reasoning', 'finalizing'];
    const index = phases.indexOf(phase);
    // Map to dots: 0% (planning), 25% (searching), 50% (drafting), 75% (reasoning), 100% (finalizing)
    return index >= 0 ? Math.min(index * 25, 100) : 10;
};

// --- Helper Functions Moved to Top Level for Reuse ---

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

            // Use brace counting to find complete JSON object
            let braceCount = 0;
            let jsonEndIndex = -1;
            for (let i = 0; i < jsonPart.length; i++) {
                if (jsonPart[i] === '{') braceCount++;
                else if (jsonPart[i] === '}') {
                    braceCount--;
                    if (braceCount === 0) {
                        jsonEndIndex = i;
                        break;
                    }
                }
            }

            if (jsonEndIndex !== -1) {
                const jsonStr = jsonPart.substring(0, jsonEndIndex + 1);
                const download = JSON.parse(jsonStr);

                // Add the implied extension from the marker if not present
                if (download && !download.type) {
                    download.type = marker === '[DOWNLOAD_PDF]' ? 'pdf' : 'docx';
                }

                // Clean content by removing the marker and JSON
                const cleanContent = content.substring(0, index).trim() || 'Report generated successfully! Click below to download.';
                return { cleanContent, download };
            }
        } catch (e) {
            console.error('❌ Failed to parse download data JSON:', e);
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

            // Use brace counting to find complete JSON object
            let braceCount = 0;
            let jsonEndIndex = -1;
            for (let i = 0; i < jsonPart.length; i++) {
                if (jsonPart[i] === '{') braceCount++;
                else if (jsonPart[i] === '}') {
                    braceCount--;
                    if (braceCount === 0) {
                        jsonEndIndex = i;
                        break;
                    }
                }
            }

            if (jsonEndIndex !== -1) {
                const jsonStr = jsonPart.substring(0, jsonEndIndex + 1);
                const verification = JSON.parse(jsonStr) as VerificationData;
                const cleanContent = content.substring(0, index).trim();
                return { cleanContent, verification };
            }
        } catch (e) {
            console.warn('Failed to parse verification data JSON:', e);
        }
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

// Helper function to format messages from backend
const formatMessagesFromBackend = (messages: BackendMessage[]): Message[] => {

    // First pass: convert all messages to Message format
    const allMessages: Message[] = messages.map((msg) => {
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
                .map((c) => typeof c === 'string' ? c : (c.text || ''))
                .join('');
        }

        if (!content.trim()) return null;

        // Extract EDIT_META from content (embedded by backend for persistence)
        // Format: [EDIT_META:{"g":"groupId","v":1,"i":0}]
        let editGroupId: string | undefined;
        let editVersion: number | undefined;
        let originalMessageIndex: number | undefined;
        let isEdit = false;

        const editMetaMatch = content.match(/\[EDIT_META:(\{[^}]+\})\]/);
        if (editMetaMatch) {
            try {
                const editMeta = JSON.parse(editMetaMatch[1]);
                editGroupId = editMeta.g;
                editVersion = editMeta.v;
                originalMessageIndex = editMeta.i;
                isEdit = true;
                // Remove the edit meta tag from content
                content = content.replace(/\[EDIT_META:\{[^}]+\}\]/, '');
            } catch (e) {
                console.warn('Failed to parse EDIT_META:', e);
            }
        }

        // Extract attachments from text prefix if present (persisted from [UPLOADED_FILES: ...])
        let attachments: { name: string; type: 'file' | 'image' }[] | undefined;
        const uploadMatch = content.match(/\[UPLOADED_FILES: (.*?)\]/);
        if (uploadMatch && uploadMatch[1]) {
            const fileList = uploadMatch[1].split(',').map(f => f.trim());
            attachments = fileList.map(name => ({
                name,
                type: name.match(/\.(jpg|jpeg|png|gif|webp)$/i) ? 'image' : 'file'
            }));
        }

        // Strip mode, persona, sites, constraint, and edit meta tags from stored messages
        content = content
            .replace(/\[MODE:.*?\]/g, '')
            .replace(/\[PERSONA:.*?\]/g, '')
            .replace(/\[UPLOADED_FILES:[\s\S]*?\]/g, '') // Use [\s\S] to match newlines if present
            .replace(/\[SITES:.*?\]/g, '')
            .replace(/\[CONSTRAINT:[\s\S]*?\]/g, '')  // May span multiple lines
            .replace(/\[EDIT_META:\{.*?\}\]/g, '')
            .trim();

        // Parse verification data from content
        const verificationParsed = parseVerificationContent(content);
        content = verificationParsed.cleanContent;
        const verificationData = verificationParsed.verification;

        // Parse download data from content
        const downloadParsed = parseDownloadContent(content);
        content = downloadParsed.cleanContent;
        const downloadData = downloadParsed.download;

        const msgAny = msg as any;
        return {
            role: isUser ? 'user' : 'agent',
            content: content,
            download: downloadData || (msgAny.download && (msgAny.download.filename || msgAny.download.data) ? {
                filename: msgAny.download.filename || '',
                data: msgAny.download.data || ''
            } : undefined),
            verification: verificationData || (msgAny.verification as VerificationData),
            attachments: attachments,
            checkpoint_id: msgAny.checkpoint_id,
            parent_checkpoint_id: msgAny.parent_checkpoint_id,
            editGroupId: editGroupId,
            currentVersionIndex: editVersion,
            isEdit: isEdit,
            originalMessageIndex: originalMessageIndex
        } as Message;
    }).filter((msg): msg is Message => msg !== null);


    // Second pass: Identify which messages are edits and group them
    // Strategy: Messages with isEdit=true should REPLACE original messages
    // originalMessageIndex refers to the Nth user message in conversation order

    // First, create a map of user message number -> array index
    const userMessageIndices: number[] = []; // userMessageIndices[n] = index in allMessages of nth user message
    allMessages.forEach((msg, idx) => {
        if (msg.role === 'user' && !msg.isEdit) {
            userMessageIndices.push(idx);
        }
    });

    // Build a map: originalMessageIndex (user msg number) -> list of edit versions
    const editsByUserMsgNum = new Map<number, Message[]>();
    const editedMessageIndices = new Set<number>(); // Indices in allMessages that are edits (to skip)

    allMessages.forEach((msg, idx) => {
        if (msg.isEdit && msg.originalMessageIndex !== undefined) {
            const userMsgNum = msg.originalMessageIndex;
            if (!editsByUserMsgNum.has(userMsgNum)) {
                editsByUserMsgNum.set(userMsgNum, []);
            }
            editsByUserMsgNum.get(userMsgNum)!.push(msg);
            editedMessageIndices.add(idx);
            // Also mark the agent response after this edit as needing special handling
            const nextIdx = idx + 1;
            if (allMessages[nextIdx]?.role === 'agent') {
                editedMessageIndices.add(nextIdx);
            }
        }
    });

    // Also mark original user messages and their agent responses as skipped if they have edits
    editsByUserMsgNum.forEach((_, userMsgNum) => {
        if (userMsgNum < userMessageIndices.length) {
            const origUserIdx = userMessageIndices[userMsgNum];
            // Mark original agent response (follows original user) as skipped
            const origAgentIdx = origUserIdx + 1;
            if (allMessages[origAgentIdx]?.role === 'agent') {
                editedMessageIndices.add(origAgentIdx);
            }
        }
    });

    console.log('📊 Edit grouping:', {
        userMessageCount: userMessageIndices.length,
        editGroups: Array.from(editsByUserMsgNum.entries()).map(([k, v]) => ({ userMsgNum: k, editCount: v.length })),
        skippedIndices: Array.from(editedMessageIndices)
    });

    // Third pass: Build final list, replacing originals with their latest edited versions
    const formattedMessages: Message[] = [];
    let userMsgCounter = 0; // Track which user message number we're on

    allMessages.forEach((msg, idx) => {
        // Skip messages that are edits (they'll replace their originals)
        if (editedMessageIndices.has(idx)) return;

        // Check if this user message has edits that should replace it
        if (msg.role === 'user') {
            const editsForThisUserMsg = editsByUserMsgNum.get(userMsgCounter);

            if (editsForThisUserMsg && editsForThisUserMsg.length > 0) {
                // This is an original message that was edited - show the latest edit with versions
                const latestEdit = editsForThisUserMsg[editsForThisUserMsg.length - 1];

                // Build versions array including the original
                const versions: import('./ThreadContextDefinition').MessageVersion[] = [
                    { userContent: msg.content, timestamp: new Date().toISOString() }
                ];

                // Get corresponding agent responses if they exist
                const nextMsgIdx = idx + 1;
                const nextMsg = allMessages[nextMsgIdx];
                if (nextMsg && nextMsg.role === 'agent') {
                    versions[0].agentContent = nextMsg.content;
                    versions[0].agentReasoning = nextMsg.reasoning;
                    versions[0].agentDownload = nextMsg.download;
                }

                // Add edited versions
                editsForThisUserMsg.forEach((editMsg) => {
                    // Find the agent response for this edit
                    const editMsgIdx = allMessages.indexOf(editMsg);
                    const editAgentMsg = allMessages[editMsgIdx + 1];

                    versions.push({
                        userContent: editMsg.content,
                        agentContent: editAgentMsg?.role === 'agent' ? editAgentMsg.content : undefined,
                        agentReasoning: editAgentMsg?.role === 'agent' ? editAgentMsg.reasoning : undefined,
                        agentDownload: editAgentMsg?.role === 'agent' ? editAgentMsg.download : undefined,
                        timestamp: new Date().toISOString()
                    });
                });

                const editGroupId = latestEdit.editGroupId || `auto_${userMsgCounter}`;

                // Push the latest user version with all versions data
                formattedMessages.push({
                    ...latestEdit,
                    versions,
                    currentVersionIndex: versions.length - 1,
                    editGroupId
                });

                // Push the latest agent version
                const latestEditIdx = allMessages.indexOf(latestEdit);
                const latestAgentMsg = allMessages[latestEditIdx + 1];
                if (latestAgentMsg && latestAgentMsg.role === 'agent') {
                    formattedMessages.push({
                        ...latestAgentMsg,
                        versions,
                        currentVersionIndex: versions.length - 1,
                        editGroupId
                    });
                } else if (nextMsg && nextMsg.role === 'agent') {
                    // Fallback to original agent response if edit doesn't have one yet
                    formattedMessages.push({
                        ...nextMsg,
                        versions,
                        currentVersionIndex: 0,
                        editGroupId
                    });
                }

                userMsgCounter++;
                return;
            }

            userMsgCounter++;
        }

        // Regular message - just add it
        formattedMessages.push(msg);
    });

    // Final pass: merge consecutive agent messages for downloads
    return formattedMessages.reduce((acc: Message[], msg) => {
        if (msg.role === 'agent') {
            const prevMsg = acc[acc.length - 1];

            if (msg.download && prevMsg && prevMsg.role === 'agent') {
                prevMsg.download = msg.download;
                if (msg.content !== 'Report generated successfully! Click below to download.') {
                    prevMsg.content = `${prevMsg.content}\n\n${msg.content}`;
                }
                return acc;
            }

            if (prevMsg && prevMsg.role === 'agent' && prevMsg.download) {
                if (prevMsg.content === 'Report generated successfully! Click below to download.') {
                    prevMsg.content = msg.content;
                    return acc;
                }
                prevMsg.content = `${prevMsg.content}\n\n${msg.content}`;
                return acc;
            }
        }

        acc.push(msg);
        return acc;
    }, []);
}

interface ThreadProviderProps {
    children: ReactNode;
}

export const ThreadProvider = ({ children }: ThreadProviderProps) => {
    const { threadId: urlThreadId } = useParams<{ threadId?: string }>();
    const navigate = useNavigate();
    const { user } = useAuth();

    const [threads, setThreads] = useState<Thread[]>([]);
    // Don't restore from localStorage until we verify the thread belongs to the current user
    const [currentThreadId, setCurrentThreadId] = useState<string | null>(null);
    const [currentMessages, setCurrentMessages] = useState<Message[]>([]);
    const [checkpoints, setCheckpoints] = useState<CheckpointInfo[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingThreads, setIsLoadingThreads] = useState(false);
    const [isLoadingMessages, setIsLoadingMessages] = useState(false);
    const [isReconnecting, setIsReconnecting] = useState(false); // Track reconnection status
    const [reconnectOnMount, setReconnectOnMount] = useState(true); // Control auto-reconnect behavior

    // Internal state for toggles (wrappers below handle logic)
    const [deepResearch, setDeepResearch_internal] = useState(false);
    const [literatureSurvey, setLiteratureSurvey_internal] = useState(false);
    const [persona, setPersona] = useState<string>(() => {
        try { return localStorage.getItem('maira_persona') || 'default'; } catch { return 'default'; }
    });
    const [isTimelineOpen, setIsTimelineOpen] = useState(false);
    const [sites, setSites] = useState<string[]>(() => {
        try {
            const cached = localStorage.getItem('maira_sites');
            return cached ? JSON.parse(cached) : [];
        } catch { return []; }
    });
    // New state to toggle site restriction without clearing the list
    const [isSiteRestrictionEnabled, setIsSiteRestrictionEnabled] = useState<boolean>(() => {
        try {
            const cached = localStorage.getItem('maira_site_restriction');
            return cached ? JSON.parse(cached) : false;
        } catch { return false; }
    });
    const [customPersonas, setCustomPersonas] = useState<CustomPersona[]>([]);
    const [showThinking, setShowThinking] = useState(false);

    // Ensure only one research mode is active at a time
    const setDeepResearch = useCallback((enabled: boolean) => {
        setDeepResearch_internal(enabled);
        if (enabled) setLiteratureSurvey_internal(false);
    }, []);

    const setLiteratureSurvey = useCallback((enabled: boolean) => {
        setLiteratureSurvey_internal(enabled);
        if (enabled) setDeepResearch_internal(false);
    }, []);
    const [lastEventId, setLastEventId] = useState<string | null>(null);
    const [activeSteps, setActiveSteps] = useState<Record<string, ActiveStep>>({});

    // Reconnection state
    const reconnectAttempts = useRef(0);
    const maxReconnectAttempts = 3;
    const abortControllerRef = useRef<AbortController | null>(null);
    // Flag to prevent re-entrancy in thread selection
    const isSelectingRef = useRef(false);

    // Persist persona to localStorage
    useEffect(() => {
        console.log('👤 Persona changed to:', persona);
        try { localStorage.setItem('maira_persona', persona); } catch { }
    }, [persona]);

    // Persist sites to localStorage (fast cache; Supabase is source of truth)
    useEffect(() => {
        try { localStorage.setItem('maira_sites', JSON.stringify(sites)); } catch { }
    }, [sites]);

    // Persist site restriction enablement
    useEffect(() => {
        try { localStorage.setItem('maira_site_restriction', JSON.stringify(isSiteRestrictionEnabled)); } catch { }
    }, [isSiteRestrictionEnabled]);

    // ── Custom Personas ──
    const loadCustomPersonas = useCallback(async () => {
        if (!user?.id) return;
        try {
            const response = await axios.get(`${API_BASE}/personas?user_id=${user.id}`);
            setCustomPersonas(response.data);
        } catch (error) {
            console.error('Failed to load custom personas:', error);
        }
    }, [user?.id]);

    const addCustomPersona = useCallback(async (name: string, instructions: string) => {
        if (!user?.id) return;
        try {
            await axios.post(`${API_BASE}/personas`, {
                user_id: user.id,
                name,
                instructions
            });
            await loadCustomPersonas();
        } catch (error) {
            console.error('Failed to create custom persona:', error);
            throw error;
        }
    }, [user?.id, loadCustomPersonas]);

    const updateCustomPersona = useCallback(async (personaId: string, name: string, instructions: string) => {
        if (!user?.id) return;
        try {
            await axios.put(`${API_BASE}/personas/${personaId}?user_id=${user.id}`, {
                name,
                instructions
            });
            await loadCustomPersonas();
        } catch (error) {
            console.error('Failed to update custom persona:', error);
            throw error;
        }
    }, [user?.id, loadCustomPersonas]);

    const deleteCustomPersona = useCallback(async (personaId: string) => {
        if (!user?.id) return;
        try {
            await axios.delete(`${API_BASE}/personas/${personaId}?user_id=${user.id}`);
            await loadCustomPersonas();
        } catch (error) {
            console.error('Failed to delete custom persona:', error);
            throw error;
        }
    }, [user?.id, loadCustomPersonas]);

    const getCustomPersonaInstructions = useCallback((personaIdentifier: string): string | null => {
        // personaIdentifier is "custom-<persona_id>"
        const id = personaIdentifier.replace('custom-', '');
        const cp = customPersonas.find(p => p.persona_id === id);
        return cp?.instructions || null;
    }, [customPersonas]);

    // ── Persistent Sites ──
    const loadSavedSites = useCallback(async () => {
        if (!user?.id) return;
        try {
            const response = await axios.get(`${API_BASE}/user-sites?user_id=${user.id}`);
            const savedSites: string[] = response.data.sites || [];
            setSites(savedSites);  // Always set — even if empty (clears stale cache)
            console.log(`🌐 Loaded ${savedSites.length} sites from Supabase`);
        } catch (error) {
            console.error('Failed to load saved sites:', error);
            // Keep localStorage-cached sites as fallback
        }
    }, [user?.id]);

    const saveSites = useCallback(async (newSites: string[]) => {
        if (!user?.id) return;
        try {
            await axios.put(`${API_BASE}/user-sites`, {
                user_id: user.id,
                urls: newSites
            });
        } catch (error) {
            console.error('Failed to save sites:', error);
        }
    }, [user?.id]);

    // Load custom personas and saved sites when user changes
    useEffect(() => {
        if (user?.id) {
            loadCustomPersonas();
            loadSavedSites();
        }
    }, [user?.id, loadCustomPersonas, loadSavedSites]);

    // Persist current thread ID to localStorage
    useEffect(() => {
        if (currentThreadId) {
            localStorage.setItem('maira_current_thread_id', currentThreadId);
        } else {
            localStorage.removeItem('maira_current_thread_id');
        }
    }, [currentThreadId]);



    // Clear state when user changes (logout or switch account)
    const prevUserIdRef = useRef<string | null>(null);
    useEffect(() => {
        if (prevUserIdRef.current !== null && prevUserIdRef.current !== user?.id) {
            // User changed - clear thread state
            console.log('👤 User changed, clearing thread state');
            setCurrentThreadId(null);
            setThreads([]);
            setCurrentMessages([]);
            localStorage.removeItem('maira_current_thread_id');
        }
        prevUserIdRef.current = user?.id ?? null;
    }, [user?.id]);

    // Fetch all threads on mount
    const refreshThreads = useCallback(async () => {
        if (!user?.id) return; // Don't fetch if no user
        setIsLoadingThreads(true);
        try {
            const response = await axios.get(`${API_BASE}/threads?user_id=${user.id}`);
            setThreads(response.data);
        } catch (error) {
            console.error('Failed to fetch threads:', error);
        } finally {
            setIsLoadingThreads(false);
        }
    }, [user?.id]);

    useEffect(() => {
        refreshThreads();
    }, [refreshThreads]);

    // Create a new thread
    const createThread = useCallback(async (title?: string): Promise<Thread> => {
        if (!user?.id) {
            throw new Error('User must be logged in to create a thread');
        }
        const response = await axios.post(`${API_BASE}/threads`, { title, user_id: user.id });
        const newThread = response.data;
        setThreads(prev => [newThread, ...prev]);
        return newThread;
    }, [user?.id]);

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

    // Select a thread and load its messages
    const selectThread = useCallback(async (threadId: string) => {
        // Guard: skip if already on this thread or if another selection is in progress
        if (isSelectingRef.current) return;

        isSelectingRef.current = true;
        setCurrentThreadId(threadId);
        setIsLoadingMessages(true);
        setIsLoading(true);

        try {
            const response = await axios.get(`${API_BASE}/threads/${threadId}/messages`);
            const messages = response.data.messages || [];
            const formattedMessages = formatMessagesFromBackend(messages);

            // Always attempt to restore downloads from Supabase for threads that have
            // agent messages. The checkpoint messages have their [DOWNLOAD_PDF] markers
            // stripped during serialisation so we cannot rely on msg.download being set
            // from content; the backend will inject a stub but we always fetch to be safe.
            const hasAgentMessages = formattedMessages.some(m => m.role === 'agent');
            if (hasAgentMessages) {
                try {
                    const dlResp = await axios.get(`${API_BASE}/threads/${threadId}/downloads`);
                    const downloads: { filename: string; data: string; file_type: string }[] =
                        dlResp.data.downloads || [];

                    if (downloads.length > 0) {
                        // Sort by filename descending (latest first) to ensure we pick newest versions
                        downloads.sort((a, b) => b.filename.localeCompare(a.filename));

                        // Pass 1: Match by filename against messages that already have a download stub
                        for (const msg of formattedMessages) {
                            if (msg.download && !msg.download.data) {
                                // Try to find a match that honors the expected file type if available
                                const expectedExt = (msg.download as any).type || (msg.download.filename.toLowerCase().endsWith('.pdf') ? 'pdf' : 'docx');

                                const match = downloads.find((d) => {
                                    const isExactMatch = d.filename === msg.download!.filename;
                                    const isBaseMatch = d.filename.replace(/\.\w+$/, '') === msg.download!.filename.replace(/\.\w+$/, '');
                                    const extensionMatches = d.filename.toLowerCase().endsWith(`.${expectedExt}`) ||
                                        (d as any).file_type === expectedExt;

                                    return isExactMatch || (isBaseMatch && extensionMatches);
                                });

                                if (match) {
                                    msg.download = { filename: match.filename, data: match.data };
                                }
                            }
                        }

                        // Pass 2: Fallback for messages with NO stubs at all (backend stripped them)
                        const hasAnyDownloadWithData = formattedMessages.some(m => m.download?.data);
                        if (!hasAnyDownloadWithData) {
                            // If NO message got a match, try to find the absolute most recent download 
                            // and attach it to the LAST agent message as a final fallback
                            const lastAgentMsg = [...formattedMessages].reverse().find(m => m.role === 'agent');
                            if (lastAgentMsg && downloads[0]) {
                                lastAgentMsg.download = {
                                    filename: downloads[0].filename,
                                    data: downloads[0].data
                                };
                            }
                        }
                    }
                } catch (dlErr) {
                    console.warn('⚠️ Could not fetch downloads from Supabase:', dlErr);
                }
            }

            setCurrentMessages(formattedMessages);
        } catch (error) {
            console.error('Failed to load thread messages:', error);
            setCurrentMessages([]);
        } finally {
            setIsLoading(false);
            setIsLoadingMessages(false);
            isSelectingRef.current = false;
        }
    }, []);

    // Reconnect to an active stream
    const reconnectToStream = useCallback(async (threadId: string) => {
        setIsReconnecting(true);
        setIsLoading(true);

        try {
            console.log('🔄 Attempting to reconnect to stream for thread:', threadId);

            // 1. First check session status to determine if deep research is active
            try {
                const statusResp = await fetch(`${API_BASE}/sessions/${threadId}/status`);
                if (statusResp.ok) {
                    const sessionStatus = await statusResp.json();
                    console.log('📊 Session status:', sessionStatus);

                    if (sessionStatus.has_active_stream && sessionStatus.deep_research) {
                        console.log('🔬 Deep research session detected, enabling toggle');
                        setDeepResearch_internal(true);
                    }

                    // If session isn't running, no need to reconnect
                    if (!sessionStatus.has_active_stream) {
                        console.log('ℹ️ Session is not running, skipping reconnect');
                        setIsReconnecting(false);
                        setIsLoading(false);
                        return;
                    }
                }
            } catch (statusErr) {
                console.warn('⚠️ Could not check session status:', statusErr);
            }

            // 2. Connect to the SSE stream
            const response = await fetch(`${API_BASE}/sessions/${threadId}/stream?from_index=0`);

            if (!response.ok) {
                // If 404 or other error, it means no active run exists
                console.log('ℹ️ No active stream found for this thread');
                setIsReconnecting(false);
                setIsLoading(false);
                return;
            }

            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let accumulatedContent = '';

            // Phase ordering for anti-regression during reconnect
            const PHASE_ORDER: Record<string, number> = { planning: 0, searching: 1, drafting: 2, reasoning: 3, finalizing: 4, completed: 5 };
            let highestPhase = '';
            let highestPhaseIdx = -1;

            if (!reader) {
                throw new Error('No response body reader available');
            }

            // Ensure we have a placeholder if needed - using functional update to get latest state
            setCurrentMessages(prev => {
                if (prev.length === 0) return prev;

                const updated = [...prev];
                const lastMsg = updated[updated.length - 1];

                // If last message is from user, append a placeholder
                if (lastMsg.role === 'user') {
                    updated.push({
                        role: 'agent',
                        content: '', // Empty initially, will be filled by stream
                        status: 'Reconnecting...',
                        type: 'streaming'
                    });
                    return updated;
                }

                // If last message is from agent but not streaming, mark it as streaming
                if (lastMsg.role === 'agent') {
                    updated[updated.length - 1] = {
                        ...lastMsg,
                        type: 'streaming',
                        status: 'Reconnecting...'
                    };
                    return updated;
                }

                return updated;
            });

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
                            // console.log('Reconnect SSE data:', data);

                            if (data.type === 'ping') continue;

                            // Handle init events — detect deep research mode
                            if (data.type === 'init') {
                                if (data.deep_research) {
                                    console.log('🔬 Reconnect: init event confirms deep research mode');
                                    setDeepResearch_internal(true);
                                }
                                // Set mode on streaming message
                                setCurrentMessages(prev => {
                                    const updated = [...prev];
                                    const lastIdx = updated.length - 1;
                                    if (updated[lastIdx]?.type === 'streaming') {
                                        updated[lastIdx] = {
                                            ...updated[lastIdx],
                                            mode: data.mode,
                                            modeDisplay: data.mode_display
                                        };
                                    }
                                    return updated;
                                });
                                continue;
                            }

                            // Handle phase events — update currentPhase on streaming message
                            if (data.type === 'phase') {
                                const { phase, name, icon, description } = data;
                                const phaseIdx = PHASE_ORDER[phase] ?? -1;

                                // Anti-regression: only advance forward
                                if (phaseIdx > highestPhaseIdx) {
                                    highestPhase = phase;
                                    highestPhaseIdx = phaseIdx;
                                }



                                setCurrentMessages(prev => {
                                    const updated = [...prev];
                                    const lastIdx = updated.length - 1;
                                    if (updated[lastIdx]?.type === 'streaming') {
                                        updated[lastIdx] = {
                                            ...updated[lastIdx],
                                            currentPhase: highestPhase,
                                            phaseName: name,
                                            phaseIcon: icon,
                                            phaseDescription: description
                                        };
                                    }
                                    return updated;
                                });
                                continue;
                            }

                            // Handle real-time status updates (Sync with sendMessage logic)
                            if (data.type === 'status') {
                                const { tool, step, message, detail, icon, phase, progress: statusProgress } = data;
                                if (tool) {
                                    // Update active steps for UI tracking
                                    const activePhase = getPhaseFromToolName(tool);
                                    const calculatedProgress = getProgressFromPhase(activePhase);

                                    setActiveSteps(prev => ({
                                        ...prev,
                                        [tool]: {
                                            id: tool,
                                            action: message || `Running ${tool}...`,
                                            status: step === 'start' ? 'running' : 'done',
                                            detail: detail || `Agent is actively working on ${tool}`,
                                            phase: activePhase,
                                            progress: calculatedProgress,
                                            timestamp: Date.now()
                                        }
                                    }));

                                    // Track phase from status events too (anti-regression)
                                    const explicitPhase = phase || activePhase;
                                    if (explicitPhase) {
                                        const phaseIdx = PHASE_ORDER[explicitPhase] ?? -1;
                                        if (phaseIdx > highestPhaseIdx) {
                                            highestPhase = explicitPhase;
                                            highestPhaseIdx = phaseIdx;
                                        }
                                    }

                                    setCurrentMessages(prev => {
                                        const updated = [...prev];
                                        const lastIdx = updated.length - 1;

                                        // Verify the last message is the one we are streaming
                                        if (updated[lastIdx]?.type === 'streaming') {
                                            const statusText = message || `Running ${tool}...`;
                                            updated[lastIdx] = {
                                                ...updated[lastIdx],
                                                status: statusText,
                                                statusDetail: detail,
                                                statusIcon: icon,
                                                currentPhase: highestPhase || updated[lastIdx].currentPhase,
                                                progress: statusProgress ?? (step === 'start' ? calculatedProgress : updated[lastIdx].progress),
                                                holdPhase: step === 'start' ? true : (updated[lastIdx].holdPhase || false),
                                                holdValue: step === 'start' ? calculatedProgress : updated[lastIdx].holdValue
                                            };
                                        }
                                        return updated;
                                    });
                                }
                                continue;
                            }

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
                                    break;
                                }
                                continue;
                            }

                            if (data.type === 'update' && data.messages) {
                                // Only process the LAST message in the update to avoid duplicating history
                                const { messages } = data;
                                if (messages.length > 0) {
                                    const msg = messages[messages.length - 1];

                                    if (msg.content && msg.type !== 'human') {
                                        accumulatedContent += msg.content;
                                        setCurrentMessages(prev => {
                                            const updated = [...prev];
                                            const lastIdx = updated.length - 1;

                                            // Handle case where we need to Append a new message vs Update existing
                                            if (updated[lastIdx]?.type === 'streaming') {
                                                updated[lastIdx] = {
                                                    ...updated[lastIdx],
                                                    content: accumulatedContent,
                                                    // Preserve existing status (e.g. "Running Tool...") unless replaying
                                                    status: data.replayed ? 'Catching up...' : updated[lastIdx].status
                                                };
                                            } else if (updated[lastIdx]?.role === 'user') {
                                                // If last was user, append new agent message
                                                updated.push({
                                                    role: 'agent',
                                                    content: accumulatedContent,
                                                    type: 'streaming',
                                                    status: 'Reconnected'
                                                });
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
            console.error('Reconnect failed:', error);
            setIsReconnecting(false);
            setIsLoading(false);
        }
    }, [currentThreadId]);

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
    }, [currentThreadId, selectThread]);

    // Track if we've already handled the initial URL thread
    const hasHandledUrlThreadRef = useRef(false);

    // PRIMARY: Restore thread from URL on mount (takes priority over localStorage)
    // This ensures reloading a page with a thread ID in the URL stays on that thread
    useEffect(() => {
        const restoreFromUrl = async () => {
            // Only run once on mount
            if (hasHandledUrlThreadRef.current) return;
            if (!user?.id) return;

            // If URL has a thread ID, prioritize it
            if (urlThreadId) {
                hasHandledUrlThreadRef.current = true;
                console.log('🔗 Restoring thread from URL:', urlThreadId);

                try {
                    // Verify thread belongs to current user
                    const response = await axios.get(`${API_BASE}/threads?user_id=${user.id}`);
                    const userThreads = response.data as Thread[];
                    const threadBelongsToUser = userThreads.some(t => t.thread_id === urlThreadId);

                    if (threadBelongsToUser) {
                        // Update localStorage to match URL
                        localStorage.setItem('maira_current_thread_id', urlThreadId);
                        // Select the thread and load its messages
                        await selectThread(urlThreadId);

                        // Attempt to reconnect if enabled
                        if (reconnectOnMount) {
                            reconnectToStream(urlThreadId);
                        }
                    } else {
                        console.log('⚠️ URL thread does not belong to current user, redirecting');
                        navigate('/chat', { replace: true });
                    }
                } catch (error) {
                    console.warn('Failed to verify URL thread:', error);
                    navigate('/chat', { replace: true });
                }
            } else {
                // No URL thread ID, try localStorage
                hasHandledUrlThreadRef.current = true;
                const savedThreadId = localStorage.getItem('maira_current_thread_id');
                if (savedThreadId) {
                    console.log('💾 Restoring thread from localStorage:', savedThreadId);

                    try {
                        const response = await axios.get(`${API_BASE}/threads?user_id=${user.id}`);
                        const userThreads = response.data as Thread[];
                        const threadBelongsToUser = userThreads.some(t => t.thread_id === savedThreadId);

                        if (threadBelongsToUser) {
                            await selectThread(savedThreadId);
                            // Update URL to match
                            navigate(`/chat/${savedThreadId}`, { replace: true });

                            // Attempt to reconnect if enabled
                            if (reconnectOnMount) {
                                reconnectToStream(savedThreadId);
                            }
                        } else {
                            console.log('⚠️ Saved thread does not belong to current user, clearing');
                            localStorage.removeItem('maira_current_thread_id');
                        }
                    } catch (error) {
                        console.warn('Failed to verify saved thread:', error);
                        localStorage.removeItem('maira_current_thread_id');
                    }
                }
            }
        };

        restoreFromUrl();
    }, [user?.id, urlThreadId, selectThread, navigate, reconnectOnMount, reconnectToStream]);

    /* 
    // Handled by restoreFromUrl now to avoid race conditions
    // Check for active session and reconnect — ONLY on initial mount
    useEffect(() => {
        const checkAndReconnect = async () => {
             // ... logic moved to restoreFromUrl ...
        };
        // checkAndReconnect();
    }, [currentThreadId, user?.id, reconnectToStream]);
    */

    // Single unified URL ↔ state sync effect
    useEffect(() => {
        // Sync state → URL
        if (currentThreadId && currentThreadId !== urlThreadId) {
            navigate(`/chat/${currentThreadId}`, { replace: true });
        } else if (!currentThreadId && urlThreadId) {
            navigate('/chat', { replace: true });
        }
        // Sync URL → state (only when user navigates to a URL with a threadId we're not on)
        else if (urlThreadId && !currentThreadId && !isReconnecting) {
            selectThread(urlThreadId);
        }
    }, [currentThreadId, urlThreadId, navigate, isReconnecting, selectThread]);

    // Delete a thread
    const deleteThread = useCallback(async (threadId: string) => {
        try {
            // Include user_id for ownership validation
            const params = user?.id ? `?user_id=${user.id}` : '';
            await axios.delete(`${API_BASE}/threads/${threadId}${params}`);
            setThreads(prev => prev.filter(t => t.thread_id !== threadId));

            // If deleted thread was current, reset to new chat
            if (currentThreadId === threadId) {
                setCurrentThreadId(null);
                setCurrentMessages([]);
                localStorage.removeItem('maira_current_thread_id');
                navigate('/chat', { replace: true });
            }
        } catch (error) {
            console.error('Failed to delete thread:', error);
        }
    }, [currentThreadId, user?.id, navigate]);

    // Start a new chat
    const startNewChat = useCallback(() => {
        setCurrentThreadId(null);
        setCheckpoints([]);
        setActiveSteps({});
        setDeepResearch_internal(false);
        setLiteratureSurvey_internal(false);
        setLastEventId(null);
        setCurrentMessages([]);
        localStorage.removeItem('maira_current_thread_id');
        navigate('/chat', { replace: true });
    }, [navigate]);

    // Stop streaming response
    const stopStream = useCallback(async () => {
        console.log('🛑 Stopping stream generation...');

        // 1. Abort frontend SSE connection
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }

        // 2. Call backend cancel endpoint to stop the agent
        if (currentThreadId) {
            try {
                await axios.post(`${API_BASE}/sessions/${currentThreadId}/cancel`);
                console.log('✅ Backend agent cancelled');
            } catch (error) {
                console.warn('Failed to cancel backend agent (may have already completed):', error);
            }
        }

        setIsLoading(false);

        // Finalize the last streaming message cleanly — preserve whatever reasoning arrived
        setCurrentMessages(prev => {
            const updated = [...prev];
            const lastIdx = updated.length - 1;
            if (lastIdx >= 0 && updated[lastIdx]?.type === 'streaming') {
                const m = updated[lastIdx];
                updated[lastIdx] = {
                    ...m,
                    type: undefined,       // Remove streaming flag so ReasoningBlock exits streaming mode
                    status: undefined,     // Clear spinner
                    // Preserve whatever reasoning was already accumulated — don't wipe it
                    reasoning: m.reasoning || undefined,
                    content: m.content
                        ? m.content + '\n\n*(Generation stopped by user)*'
                        : '*(Generation stopped by user)*'
                };
            }
            return updated;
        });

        setActiveSteps({});
    }, [currentThreadId]);

    // Send a message with SSE streaming
    const sendMessage = useCallback(async (prompt: string, parentCheckpointId?: string, attachments?: { name: string; type: 'file' | 'image' }[], skipMessageAdd = false) => {
        if (!prompt.trim() || isLoading) return;

        // Require user to be logged in for new threads
        if (!currentThreadId && !user?.id) {
            console.error('User must be logged in to start a new chat');
            return;
        }

        // Cancel any existing request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        // Clear active steps from previous run
        setActiveSteps({});

        // Build the prompt the agent actually sees — prefix with file context
        let agentPrompt = prompt;
        if (attachments && attachments.length > 0) {
            const fileList = attachments.map(a => a.name).join(', ');
            agentPrompt = `[UPLOADED_FILES: ${fileList}]\n${prompt}`;
        }

        // Add user message immediately and finalize any interrupted streaming messages
        if (!skipMessageAdd) {
            setCurrentMessages(prev => {
                const sanitized = prev.map(m => {
                    if (m.type === 'streaming') {
                        return {
                            ...m,
                            type: undefined, // Remove streaming type
                            status: 'Interrupted',
                            content: m.content ? m.content + "\n\n(Interrupted)" : "(Interrupted)"
                        };
                    }
                    return m;
                });
                return [...sanitized, { role: 'user', content: prompt, attachments }];
            });
        }
        setIsLoading(true);

        let newThreadId = currentThreadId;
        let accumulatedContent = '';
        let accumulatedReasoning = '';
        let hasReceivedReasoning = false; // Track if reasoning was actually received this session
        let buffer = ''; // Buffer for incomplete SSE lines
        let downloadData: { filename: string; data: string } | undefined = undefined;
        let verificationData: VerificationData | undefined = undefined;
        let responseComplete = false; // Track when we have a complete response
        const seenContentHashes = new Set<string>(); // Deduplicate content from backend

        // Unique session ID to prevent race conditions with previous requests
        const streamingSessionId = `stream_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;



        // Reconnection logic
        const connectStream = async (retryCount = 0): Promise<void> => {
            try {
                const requestBody: Record<string, unknown> = {
                    prompt: agentPrompt,
                    thread_id: currentThreadId,
                    user_id: user?.id, // Required for new thread creation + multi-tenant RAG
                    deep_research: deepResearch, // Pass the deepResearch toggle state
                    literature_survey: literatureSurvey, // Pass literature survey toggle state
                    persona: persona, // Pass selected persona
                    sites: ((deepResearch || literatureSurvey) && isSiteRestrictionEnabled && sites.length > 0) ? sites : undefined, // Only pass sites if enabled and non-empty
                };
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
                // Explicitly set reasoning to undefined to prevent showing stale reasoning from previous messages
                // Include streamingSessionId to prevent race conditions with previous requests
                if (retryCount === 0) {
                    setCurrentMessages(prev => [...prev, {
                        role: 'agent',
                        content: '',
                        // Fix for UI jumping to "Reasoning" phase due to "Thinking..." status match
                        status: deepResearch ? 'Planning Strategy...' : 'Thinking...',
                        progress: 0,
                        type: 'streaming',
                        currentPhase: deepResearch ? 'planning' : undefined,
                        reasoning: undefined,
                        message_id: streamingSessionId  // Unique ID for this streaming session
                    }]);
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
                                // Skip ping events (keepalive)
                                if (data.type === 'ping') continue;

                                // Track event ID for reconnection
                                if (data.event_id) {
                                    setLastEventId(data.event_id);
                                }

                                // Handle already_running status (session reconnect)
                                if (data.status === 'already_running') {
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

                                    // Store mode info from init event for deep research UI
                                    if (data.mode) {
                                        setCurrentMessages(prev => {
                                            const updated = [...prev];
                                            const streamingIdx = updated.findIndex(m => m.message_id === streamingSessionId && m.type === 'streaming');
                                            if (streamingIdx !== -1) {
                                                updated[streamingIdx] = {
                                                    ...updated[streamingIdx],
                                                    mode: data.mode,
                                                    modeDisplay: data.mode_display
                                                };
                                            }
                                            return updated;
                                        });
                                    }
                                } else if (data.type === 'phase') {
                                    // Handle phase transitions from backend (deep research phases)
                                    const { phase, name, icon, description } = data;
                                    // Phase ordering for anti-regression
                                    const PHASE_ORDER: Record<string, number> = { planning: 0, searching: 1, analyzing: 2, drafting: 3, reasoning: 4, finalizing: 5 };

                                    setCurrentMessages(prev => {
                                        const updated = [...prev];
                                        const streamingIdx = updated.findIndex(m => m.message_id === streamingSessionId && m.type === 'streaming');
                                        if (streamingIdx !== -1) {
                                            // Anti-regression: only advance phase forward
                                            const currentIdx = PHASE_ORDER[updated[streamingIdx].currentPhase as string] ?? -1;
                                            const newIdx = PHASE_ORDER[phase] ?? -1;
                                            if (newIdx >= currentIdx) {
                                                updated[streamingIdx] = {
                                                    ...updated[streamingIdx],
                                                    currentPhase: phase,
                                                    phaseName: name,
                                                    phaseIcon: icon,
                                                    phaseDescription: description
                                                };
                                            }
                                        }
                                        return updated;
                                    });
                                } else if (data.type === 'thinking') {
                                    // Handle thinking/reasoning blocks from backend
                                    const thinkingContent = data.content || '';
                                    if (thinkingContent) {
                                        accumulatedReasoning += thinkingContent;
                                        hasReceivedReasoning = true;
                                    }

                                    setCurrentMessages(prev => {
                                        const updated = [...prev];
                                        const streamingIdx = updated.findIndex(m => m.message_id === streamingSessionId && m.type === 'streaming');
                                        if (streamingIdx !== -1) {
                                            const msg = updated[streamingIdx];
                                            const PHASE_ORDER: Record<string, number> = { planning: 0, searching: 1, drafting: 2, reasoning: 3, finalizing: 4, completed: 5 };

                                            // Anti-regression for phase: don't let a thinking event move us backwards
                                            const newPhase = data.phase || msg.currentPhase;
                                            const safePhase = (newPhase && msg.currentPhase)
                                                ? (PHASE_ORDER[newPhase as string] ?? -1) >= (PHASE_ORDER[msg.currentPhase as string] ?? -1)
                                                    ? newPhase
                                                    : msg.currentPhase
                                                : (newPhase || msg.currentPhase);

                                            // Determine updated status: preserve specific research status messages
                                            const currentStatus = msg.status || '';
                                            const isGenericStatus = currentStatus === 'Thinking...' || currentStatus === '💭 Thinking...' || currentStatus.includes('Strategy...');
                                            const newStatus = (deepResearch && !isGenericStatus) ? currentStatus : '💭 Thinking...';

                                            updated[streamingIdx] = {
                                                ...msg,
                                                reasoning: hasReceivedReasoning ? accumulatedReasoning : undefined,
                                                status: newStatus,
                                                currentPhase: safePhase as any
                                            };
                                        }
                                        return updated;
                                    });
                                } else if (data.type === 'status') {
                                    // Handle real-time status updates for tools/subagents
                                    // Enhanced: now includes detail, icon, phase from backend
                                    const { tool, step, message, progress, detail, icon, phase } = data;
                                    if (tool) {
                                        const activePhase = getPhaseFromToolName(tool);
                                        const calculatedProgress = getProgressFromPhase(activePhase);

                                        setActiveSteps(prev => ({
                                            ...prev,
                                            [tool]: {
                                                id: tool,
                                                action: message || `Running ${tool}...`,
                                                status: step === 'start' ? 'running' : 'done',
                                                detail: detail || `Agent is actively working on ${tool}`,
                                                phase: activePhase,
                                                progress: calculatedProgress,
                                                timestamp: Date.now()
                                            }
                                        }));

                                        setCurrentMessages(prev => {
                                            const updated = [...prev];
                                            const streamingIdx = updated.findIndex(m => m.message_id === streamingSessionId && m.type === 'streaming');
                                            if (streamingIdx === -1) return prev;

                                            // Determine new status text
                                            const statusText = message || `Running ${tool}...`;

                                            // Anti-regression: only advance phase forward, never go back
                                            const PHASE_ORDER: Record<string, number> = { planning: 0, searching: 1, analyzing: 2, drafting: 3, reasoning: 4, finalizing: 5 };
                                            const existingPhase = updated[streamingIdx].currentPhase as string;

                                            // Determine the best phase to apply
                                            const phaseToApply = phase || activePhase;
                                            const safePhase = phaseToApply
                                                ? (PHASE_ORDER[phaseToApply] ?? -1) >= (PHASE_ORDER[existingPhase] ?? -1)
                                                    ? phaseToApply
                                                    : existingPhase
                                                : existingPhase;

                                            // Update the streaming message with enhanced status info from backend
                                            updated[streamingIdx] = {
                                                ...updated[streamingIdx],
                                                status: statusText,
                                                statusDetail: detail,  // Additional detail from backend
                                                statusIcon: icon,      // Icon emoji from backend
                                                // Update phase only if it moves forward
                                                currentPhase: safePhase,
                                                // Only set/override progress when a mapped phase indicates start
                                                progress: (step === 'start') ? calculatedProgress : (progress || updated[streamingIdx].progress),
                                                // hold the phase to prevent simulated progress from advancing past this phase
                                                holdPhase: step === 'start' ? true : (updated[streamingIdx].holdPhase || false),
                                                holdValue: step === 'start' ? calculatedProgress : updated[streamingIdx].holdValue,
                                                // keep reasoning only if new reasoning arrived in this session
                                                reasoning: hasReceivedReasoning ? accumulatedReasoning : undefined
                                            };

                                            return updated;
                                        });
                                    }
                                } else if (data.type === 'reasoning') {
                                    // Handle reasoning/thinking blocks separately
                                    const reasoningText = data.content || '';
                                    if (reasoningText) {
                                        accumulatedReasoning += reasoningText;
                                        hasReceivedReasoning = true; // Mark that we received actual reasoning
                                    }

                                    setCurrentMessages(prev => {
                                        const updated = [...prev];
                                        const streamingIdx = updated.findIndex(m => m.message_id === streamingSessionId && m.type === 'streaming');
                                        if (streamingIdx !== -1) {
                                            updated[streamingIdx] = {
                                                ...updated[streamingIdx],
                                                reasoning: hasReceivedReasoning ? accumulatedReasoning : undefined,
                                                status: '💭 Thinking...'
                                            };
                                        }
                                        return updated;
                                    });
                                } else if (data.type === 'download') {
                                    // Handle download event directly from backend (bypasses LLM corruption)
                                    if (data.filename && data.data) {
                                        downloadData = {
                                            filename: data.filename,
                                            data: data.data
                                        };
                                        // Update the current message with download data
                                        setCurrentMessages(prev => {
                                            const updated = [...prev];
                                            const streamingIdx = updated.findIndex(m => m.message_id === streamingSessionId);
                                            if (streamingIdx !== -1) {
                                                updated[streamingIdx] = {
                                                    ...updated[streamingIdx],
                                                    download: downloadData
                                                };
                                            }
                                            return updated;
                                        });
                                    }
                                } else if (data.type === 'update' && data.messages) {
                                    // Process messages from the update
                                    for (const msg of data.messages) {
                                        // Helper to extract content (handles array format from Gemini)
                                        const extractContent = (content: string | Array<{ text?: string }>): string => {
                                            if (typeof content === 'string') return content;
                                            if (Array.isArray(content)) {
                                                return content
                                                    .map(c => c.text || '')
                                                    .join('');
                                            }
                                            return '';
                                        };

                                        // Check if this is a tool call (show status)
                                        if (msg.tool_calls && msg.tool_calls.length > 0) {
                                            const toolNames = msg.tool_calls.map((tc: { name: string }) => tc.name);
                                            const status = getVerificationStatus(toolNames);

                                            // Check if this is a verification tool - set verifying status
                                            const verificationTools = ['validate_citations', 'fact_check_claims', 'assess_content_quality', 'cross_reference_sources', 'verify_draft_completeness'];
                                            const isVerifying = toolNames.some((name: string) => verificationTools.includes(name));

                                            setCurrentMessages(prev => {
                                                const updated = [...prev];
                                                const streamingIdx = updated.findIndex(m => m.message_id === streamingSessionId && m.type === 'streaming');
                                                if (streamingIdx !== -1) {
                                                    updated[streamingIdx] = {
                                                        ...updated[streamingIdx],
                                                        status,
                                                        verification: isVerifying ? {
                                                            ...updated[streamingIdx].verification,
                                                            status: 'VERIFYING',
                                                            overallScore: 0,
                                                            timestamp: new Date().toISOString()
                                                        } : updated[streamingIdx].verification
                                                    };
                                                }
                                                return updated;
                                            });
                                        }
                                        else if (msg.content && msg.type !== 'human') {
                                            const textContent = extractContent(msg.content);
                                            let cleanContent = textContent
                                                .replace(/\[MODE:.*?\]/g, '')
                                                .replace(/\[PERSONA:.*?\]/g, '')  // Strip persona tags
                                                .trim();

                                            if (cleanContent) {
                                                // Deduplicate: skip content we've already processed
                                                // Use first 200 chars as fingerprint (matches backend logic)
                                                const contentFingerprint = cleanContent.substring(0, 200);
                                                if (seenContentHashes.has(contentFingerprint)) {
                                                    console.log('⏭️ Skipping duplicate content on frontend');
                                                    continue;
                                                }
                                                seenContentHashes.add(contentFingerprint);

                                                // Parse verification data first
                                                const verificationParsed = parseVerificationContent(cleanContent);
                                                cleanContent = verificationParsed.cleanContent;
                                                if (verificationParsed.verification) {
                                                    verificationData = verificationParsed.verification;
                                                }

                                                const parsed = parseDownloadContent(cleanContent);

                                                // Main agent content - accumulate it
                                                // Only add non-empty, non-placeholder content
                                                if (parsed.cleanContent &&
                                                    parsed.cleanContent !== 'Report generated successfully! Click below to download.') {
                                                    // Add separator if we already have content
                                                    if (accumulatedContent && !accumulatedContent.endsWith('\n\n')) {
                                                        accumulatedContent += '\n\n';
                                                    }
                                                    accumulatedContent += parsed.cleanContent;
                                                }

                                                if (parsed.download) {
                                                    downloadData = parsed.download;
                                                    // Don't set responseComplete here - wait for 'done' event
                                                    console.log("📥 Download data received, waiting for done event");
                                                }

                                                // Only update UI if we have meaningful content OR the response is complete
                                                // This prevents showing partial "Thinking..." states after content arrives
                                                const hasContent = accumulatedContent.length > 50; // Minimum meaningful content

                                                setCurrentMessages(prev => {
                                                    const updated = [...prev];
                                                    // Find the message with matching streamingSessionId to avoid race conditions
                                                    const streamingIdx = updated.findIndex(m => m.message_id === streamingSessionId && m.type === 'streaming');
                                                    if (streamingIdx !== -1) {
                                                        // Show content progressively, but keep streaming state until done
                                                        // Preserve existing progress/hold flags from previous streaming state
                                                        const prev = updated[streamingIdx];
                                                        updated[streamingIdx] = {
                                                            ...prev,
                                                            role: 'agent',
                                                            message_id: streamingSessionId,
                                                            content: accumulatedContent || '',
                                                            status: hasContent ? undefined : prev.status, // Keep status if no real content yet
                                                            reasoning: hasReceivedReasoning ? accumulatedReasoning : undefined, // Never inherit stale reasoning from the previous message
                                                            download: downloadData || prev.download,
                                                            verification: verificationData || prev.verification,
                                                            type: 'streaming' // Always stay streaming until done event
                                                        };
                                                    }
                                                    return updated;
                                                });
                                            }
                                        }
                                    }
                                } else if (data.type === 'done' || data.type === 'cancelled') {
                                    // Finalize the message and stop loading
                                    responseComplete = true;
                                    setIsLoading(false);

                                    // Clear active steps when done
                                    setActiveSteps({});

                                    const isCancelled = data.type === 'cancelled';
                                    console.log(isCancelled ? '⛔ Cancelled event received' : '✅ Done event received', 'Content length:', accumulatedContent.length);

                                    setCurrentMessages(prev => {
                                        const updated = [...prev];
                                        const streamingIdx = updated.findIndex(m => m.message_id === streamingSessionId);
                                        if (streamingIdx !== -1 && updated[streamingIdx]?.role === 'agent') {
                                            let finalContent = accumulatedContent || updated[streamingIdx].content;

                                            if (!finalContent && (downloadData || updated[streamingIdx].download)) {
                                                finalContent = 'Report generated successfully! Click below to download.';
                                            } else if (!finalContent && isCancelled) {
                                                finalContent = '*(Generation stopped)*';
                                            } else if (!finalContent) {
                                                finalContent = "I couldn't generate a response.";
                                            }

                                            updated[streamingIdx] = {
                                                ...updated[streamingIdx],
                                                type: undefined,    // Exit streaming mode — ReasoningBlock stops its timer
                                                content: finalContent,
                                                status: undefined,
                                                // Only carry reasoning if it actually arrived this session
                                                reasoning: hasReceivedReasoning ? accumulatedReasoning : undefined,
                                                download: downloadData || updated[streamingIdx].download,
                                                verification: verificationData || updated[streamingIdx].verification,
                                                holdPhase: false,
                                                holdValue: undefined
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
                                        const streamingIdx = updated.findIndex(m => m.message_id === streamingSessionId && m.type === 'streaming');
                                        if (streamingIdx !== -1) {
                                            updated[streamingIdx] = {
                                                ...updated[streamingIdx],
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
                                        const streamingIdx = updated.findIndex(m => m.message_id === streamingSessionId && m.type === 'streaming');
                                        if (streamingIdx !== -1) {
                                            // Replace streaming message with error message
                                            updated[streamingIdx] = {
                                                role: 'agent',
                                                message_id: streamingSessionId,
                                                content: `⚠️ An error occurred: ${data.error}\n\nPlease try again or rephrase your request.`,
                                                type: undefined,
                                                status: undefined,
                                                holdPhase: false,
                                                holdValue: undefined
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

            } catch (error: unknown) {
                const err = error as Error;
                // Check if error is due to abort (user cancelled)
                if (err.name === 'AbortError') {
                    console.log('Request aborted by user');
                    setIsLoading(false);
                    return;
                }

                // Attempt reconnection only for network errors, not agent errors
                const isAgentError = err.message && err.message.includes('Agent error');
                if (!isAgentError && retryCount < maxReconnectAttempts && !responseComplete) {
                    console.log(`Connection lost, attempting reconnect (${retryCount + 1}/${maxReconnectAttempts})...`);
                    reconnectAttempts.current = retryCount + 1;
                    await new Promise(resolve => setTimeout(resolve, 1000 * (retryCount + 1))); // Exponential backoff
                    return connectStream(retryCount + 1);
                }

                console.error('Error sending message:', err);
                setIsLoading(false);  // Ensure loading is stopped
                setCurrentMessages(prev => {
                    // Remove streaming placeholder if exists
                    const filtered = prev.filter(m => m.type !== 'streaming');
                    return [...filtered, {
                        role: 'agent',
                        content: `⚠️ ${isAgentError ? 'Agent error' : 'Connection error'}: ${err.message || 'Please try again.'}`
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

    }, [currentThreadId, isLoading, refreshThreads, deepResearch, literatureSurvey, persona, lastEventId, user?.id]);

    // Navigate between versions of an edited message
    const setMessageVersion = useCallback((messageIndex: number, versionIndex: number) => {
        setCurrentMessages(prev => {
            const updated = [...prev];
            const userMsg = updated[messageIndex];

            if (!userMsg || userMsg.role !== 'user' || !userMsg.versions) return prev;

            // Clamp versionIndex to valid range
            const clampedIndex = Math.max(0, Math.min(versionIndex, userMsg.versions.length - 1));
            const version = userMsg.versions[clampedIndex];

            // Update user message content and version index
            updated[messageIndex] = {
                ...userMsg,
                content: version.userContent,
                currentVersionIndex: clampedIndex
            };

            // Find the corresponding agent response (next message with same editGroupId)
            const agentMsgIndex = messageIndex + 1;
            if (agentMsgIndex < updated.length && updated[agentMsgIndex]?.role === 'agent' &&
                updated[agentMsgIndex]?.editGroupId === userMsg.editGroupId) {
                updated[agentMsgIndex] = {
                    ...updated[agentMsgIndex],
                    content: version.agentContent || '',
                    reasoning: version.agentReasoning,
                    download: version.agentDownload,
                    verification: version.agentVerification,
                    currentVersionIndex: clampedIndex
                };
            }

            return updated;
        });
    }, []);

    // Edit a message and trigger regeneration - stores versions like ChatGPT
    const editMessage = useCallback(async (messageIndex: number, newContent: string, parentCheckpointIdOverride?: string) => {
        if (isLoading) return;

        // Get the message to edit
        const messageToEdit = currentMessages[messageIndex];
        if (!messageToEdit || messageToEdit.role !== 'user') return;

        // Skip if content is the same - unless we are forcing a branch via override
        if (!parentCheckpointIdOverride && messageToEdit.content.trim() === newContent.trim()) return;

        // Get checkpoint ID: prioritized explicit override, then previous message's checkpoint
        const previousMessage = messageIndex > 0 ? currentMessages[messageIndex - 1] : null;
        const parentCheckpointId = parentCheckpointIdOverride || previousMessage?.checkpoint_id;

        // Find the corresponding agent response
        const agentMsgIndex = messageIndex + 1;
        const agentResponse = agentMsgIndex < currentMessages.length && currentMessages[agentMsgIndex]?.role === 'agent'
            ? currentMessages[agentMsgIndex]
            : null;

        // Create unique group ID for this message pair (if not already set)
        const editGroupId = messageToEdit.editGroupId || `edit_${Date.now()}_${messageIndex}`;

        // Build versions array
        const existingVersions = messageToEdit.versions || [];
        // If this is the first edit, save the original as version 0
        let versions: MessageVersion[] = [...existingVersions];
        if (versions.length === 0) {
            versions.push({
                userContent: messageToEdit.content,
                agentContent: agentResponse?.content,
                agentReasoning: agentResponse?.reasoning,
                agentDownload: agentResponse?.download,
                agentVerification: agentResponse?.verification,
                timestamp: new Date().toISOString()
            });
        }

        // Add the new edited version
        const newVersionIndex = versions.length;
        versions.push({
            userContent: newContent,
            agentContent: undefined, // Will be populated when response arrives
            timestamp: new Date().toISOString()
        });

        // Update messages in place with versioning info
        setCurrentMessages(prev => {
            const updated = [...prev];

            // Update user message with version info
            updated[messageIndex] = {
                ...messageToEdit,
                content: newContent,
                editGroupId,
                versions,
                currentVersionIndex: newVersionIndex
            };

            // Update or create agent response placeholder
            if (agentResponse) {
                updated[agentMsgIndex] = {
                    ...agentResponse,
                    content: '',
                    editGroupId,
                    versions, // Share versions reference
                    currentVersionIndex: newVersionIndex,
                    type: 'streaming',
                    status: 'Regenerating...'
                };
                // Remove any messages after the agent response (we're branching)
                return updated.slice(0, agentMsgIndex + 1);
            } else {
                // No existing agent response, add a placeholder
                const agentPlaceholder: Message = {
                    role: 'agent',
                    content: '',
                    editGroupId,
                    versions,
                    currentVersionIndex: newVersionIndex,
                    type: 'streaming',
                    status: 'Thinking...'
                };
                return [...updated.slice(0, messageIndex + 1), agentPlaceholder];
            }
        });

        // Now send the edited message and capture the response
        // We need a custom handler to update the version's agent response
        if (!currentThreadId && !user?.id) {
            console.error('User must be logged in to edit messages');
            return;
        }

        // Cancel any existing request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();
        setIsLoading(true);

        let accumulatedContent = '';
        let accumulatedReasoning = '';          // Reset per edit session — no stale bleed
        let hasEditReasoning = false;            // Guard: only show reasoning that arrived THIS edit session
        let downloadData: { filename: string; data: string } | undefined = undefined;
        let verificationData: VerificationData | undefined = undefined;

        try {
            const response = await fetch(`${API_BASE}/run-agent`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt: newContent,
                    thread_id: currentThreadId,
                    user_id: user?.id,
                    deep_research: deepResearch,
                    literature_survey: literatureSurvey,
                    persona,
                    parent_checkpoint_id: parentCheckpointId,
                    // Edit versioning metadata
                    edit_group_id: editGroupId,
                    edit_version: newVersionIndex,
                    original_message_index: messageIndex
                }),
                signal: abortControllerRef.current.signal
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            if (!response.body) throw new Error('No response body');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const jsonStr = line.slice(6).trim();
                    if (!jsonStr || jsonStr === '[DONE]') continue;

                    try {
                        const event = JSON.parse(jsonStr);

                        // Handle both 'thinking' (live stream) and 'reasoning' (batch) events
                        if ((event.type === 'thinking' || event.type === 'reasoning') && event.content) {
                            accumulatedReasoning += event.content;
                            hasEditReasoning = true;
                        }

                        if (event.type === 'download' && event.filename && event.data) {
                            downloadData = { filename: event.filename, data: event.data };
                        }

                        if (event.type === 'verification' && event.data) {
                            verificationData = event.data;
                        }

                        if (event.messages) {
                            for (const msg of event.messages) {
                                if (msg.role === 'assistant' || msg.type === 'ai') {
                                    let content = '';
                                    if (typeof msg.content === 'string') {
                                        content = msg.content;
                                    } else if (Array.isArray(msg.content)) {
                                        content = msg.content.map((c: { text?: string }) => c.text || '').join('');
                                    }
                                    if (content) {
                                        // Clean content
                                        content = content
                                            .replace(/\[MODE:.*?\]/g, '')
                                            .replace(/\[SUBAGENT:.*?\]/g, '')
                                            .replace(/\[PERSONA:.*?\]/g, '')
                                            .trim();
                                        accumulatedContent = content;

                                        // Update streaming message
                                        setCurrentMessages(prev => {
                                            const updated = [...prev];
                                            const agentIdx = updated.findIndex(
                                                (m, i) => i >= messageIndex && m.role === 'agent' && m.editGroupId === editGroupId
                                            );
                                            if (agentIdx !== -1) {
                                                updated[agentIdx] = {
                                                    ...updated[agentIdx],
                                                    content: accumulatedContent,
                                                    // Never inherit reasoning from previous version — only show what arrived this edit
                                                    reasoning: hasEditReasoning ? accumulatedReasoning : undefined,
                                                    type: 'streaming',
                                                    status: undefined
                                                };
                                            }
                                            return updated;
                                        });
                                    }
                                }
                            }
                        }

                        if (event.type === 'done' || event.type === 'error') {
                            // Finalize the version's agent response
                            setCurrentMessages(prev => {
                                const updated = [...prev];
                                const userMsgIdx = updated.findIndex(
                                    (m) => m.role === 'user' && m.editGroupId === editGroupId
                                );
                                if (userMsgIdx !== -1 && updated[userMsgIdx].versions) {
                                    const versionsCopy = [...updated[userMsgIdx].versions!];
                                    const vIdx = updated[userMsgIdx].currentVersionIndex ?? versionsCopy.length - 1;
                                    if (versionsCopy[vIdx]) {
                                        versionsCopy[vIdx] = {
                                            ...versionsCopy[vIdx],
                                            agentContent: accumulatedContent,
                                            // Only persist reasoning that actually arrived this edit session
                                            agentReasoning: hasEditReasoning ? accumulatedReasoning : undefined,
                                            agentDownload: downloadData,
                                            agentVerification: verificationData
                                        };
                                    }
                                    updated[userMsgIdx] = { ...updated[userMsgIdx], versions: versionsCopy };

                                    // Also update the agent message
                                    const agentIdx = userMsgIdx + 1;
                                    if (agentIdx < updated.length && updated[agentIdx]?.editGroupId === editGroupId) {
                                        updated[agentIdx] = {
                                            ...updated[agentIdx],
                                            content: accumulatedContent,
                                            reasoning: hasEditReasoning ? accumulatedReasoning : undefined,
                                            download: downloadData,
                                            verification: verificationData,
                                            versions: versionsCopy,
                                            type: undefined,   // Exit streaming mode cleanly
                                            status: undefined
                                        };
                                    }
                                }
                                return updated;
                            });
                            break;
                        }
                    } catch (e) {
                        console.warn('Failed to parse SSE event:', e);
                    }
                }
            }
        } catch (error) {
            if ((error as Error).name !== 'AbortError') {
                console.error('Edit message error:', error);
            }
        } finally {
            setIsLoading(false);
            abortControllerRef.current = null;
        }
    }, [currentMessages, isLoading, currentThreadId, user?.id, deepResearch, literatureSurvey, persona, sites]);

    // Helper to add upload messages (user notification + agent acknowledgment) to UI
    const addUploadMessage = useCallback((filename: string, type: 'document' | 'image') => {
        const userMsg: Message = {
            role: 'user',
            content: `📎 Uploaded ${type}: **${filename}**`,
            type: 'final'
        };
        const agentMsg: Message = {
            role: 'agent',
            content: `I've received your ${type} **${filename}** and added it to the knowledge base. You can now ask me questions about it!`,
            type: 'final'
        };
        setCurrentMessages(prev => [...prev, userMsg, agentMsg]);
    }, []);

    const uploadFile = useCallback(async (file: File) => {
        if (!user?.id) {
            toast.error("Please log in to upload documents");
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('user_id', user.id);
        if (currentThreadId) formData.append('thread_id', currentThreadId);

        const toastId = toast.loading(`Uploading ${file.name}...`);

        try {
            await axios.post(`${API_BASE}/documents/upload`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            toast.success(`Successfully uploaded ${file.name}`, { id: toastId });
        } catch (error) {
            console.error('Upload failed:', error);
            toast.error(`Failed to upload ${file.name}`, { id: toastId });
        }
    }, [user?.id, currentThreadId, addUploadMessage]);

    const uploadImage = useCallback(async (file: File, description?: string) => {
        if (!user?.id) {
            toast.error("Please log in to upload images");
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('user_id', user.id);
        if (currentThreadId) formData.append('thread_id', currentThreadId);
        if (description) formData.append('description', description);

        const toastId = toast.loading(`Uploading image ${file.name}...`);

        try {
            await axios.post(`${API_BASE}/documents/upload-image`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            toast.success(`Successfully uploaded ${file.name}`, { id: toastId });
        } catch (error) {
            console.error('Upload failed:', error);
            toast.error(`Failed to upload ${file.name}`, { id: toastId });
        }
    }, [user?.id, currentThreadId, addUploadMessage]);

    const getMessageMetadata = useCallback((message: Message, index: number): MessageMetadata => {
        return {
            messageId: message.message_id,
            checkpointId: message.checkpoint_id,
            // For user messages, the parent checkpoint is the one before it
            parentCheckpointId: message.parent_checkpoint_id || (index > 0 ? currentMessages[index - 1]?.checkpoint_id : undefined),
            timestamp: message.versions?.[message.currentVersionIndex || 0]?.timestamp,
            editGroupId: message.editGroupId,
            versionIndex: message.currentVersionIndex,
            totalVersions: message.versions?.length
        };
    }, [currentMessages]);

    // Retry a message - find the preceding user message and resend it
    const retryMessage = useCallback(async (messageIndex: number) => {
        if (isLoading) return;

        const aiMessage = currentMessages[messageIndex];
        if (!aiMessage || aiMessage.role !== 'agent') return;

        // Find the preceding user message
        const userMsgIndex = messageIndex - 1;
        const userMessage = userMsgIndex >= 0 ? currentMessages[userMsgIndex] : null;

        if (!userMessage || userMessage.role !== 'user') return;

        // Remove the failed agent message and any subsequent messages (if any)
        setCurrentMessages(prev => prev.slice(0, messageIndex));

        // Call sendMessage with the original prompt, parent checkpoint, and any attachments
        // Use skipMessageAdd=true because the user message is already in currentMessages
        await sendMessage(userMessage.content, userMessage.parent_checkpoint_id, userMessage.attachments, true);
    }, [currentMessages, isLoading, sendMessage]);

    // Backend readiness check
    const [isBackendReady, setIsBackendReady] = useState(false);

    useEffect(() => {
        let mounted = true;
        let timeoutId: ReturnType<typeof setTimeout>;

        const checkHealth = async () => {
            try {
                const res = await fetch(`${API_BASE}/health`);
                if (mounted) {
                    setIsBackendReady(res.ok);
                }
                // Periodic check every 10s if healthy, 2s if not
                const delay = res.ok ? 10000 : 2000;
                if (mounted) {
                    timeoutId = setTimeout(checkHealth, delay);
                }
            } catch (e) {
                if (mounted) {
                    setIsBackendReady(false);
                    timeoutId = setTimeout(checkHealth, 2000);
                }
            }
        };

        checkHealth();

        return () => {
            mounted = false;
            if (timeoutId) clearTimeout(timeoutId);
        };
    }, []);

    const value = useMemo<ThreadContextType>(() => ({
        threads,
        currentThreadId,
        currentMessages,
        checkpoints,
        isLoading,
        isLoadingThreads,
        isLoadingMessages,
        isReconnecting,
        reconnectOnMount,
        deepResearch,
        literatureSurvey,
        persona,
        sites,
        lastEventId,
        activeSteps,
        showThinking,
        createThread,
        selectThread,
        deleteThread,
        refreshThreads,
        sendMessage,
        editMessage,
        setMessageVersion,
        getMessageMetadata,
        startNewChat,
        setDeepResearch,
        setLiteratureSurvey,
        setPersona,
        setSites,
        isSiteRestrictionEnabled,
        setIsSiteRestrictionEnabled,
        customPersonas,
        addCustomPersona,
        updateCustomPersona,
        deleteCustomPersona,
        getCustomPersonaInstructions,
        loadSavedSites,
        saveSites,
        setShowThinking,
        setReconnectOnMount,
        fetchStateHistory,
        branchFromCheckpoint,
        stopStream,
        retryMessage,
        uploadFile,
        uploadImage,
        isTimelineOpen,
        setIsTimelineOpen,
        isBackendReady
    }), [
        threads,
        currentThreadId,
        currentMessages,
        checkpoints,
        isLoading,
        isLoadingThreads,
        isLoadingMessages,
        isReconnecting,
        reconnectOnMount,
        deepResearch,
        literatureSurvey,
        persona,
        sites,
        lastEventId,
        activeSteps,
        showThinking,
        createThread,
        selectThread,
        deleteThread,
        refreshThreads,
        sendMessage,
        editMessage,
        setMessageVersion,
        getMessageMetadata,
        startNewChat,
        setDeepResearch,
        setLiteratureSurvey,
        setPersona,
        setSites,
        isSiteRestrictionEnabled,
        setIsSiteRestrictionEnabled,
        customPersonas,
        addCustomPersona,
        updateCustomPersona,
        deleteCustomPersona,
        getCustomPersonaInstructions,
        loadSavedSites,
        saveSites,
        setShowThinking,
        setReconnectOnMount,
        fetchStateHistory,
        branchFromCheckpoint,
        stopStream,
        retryMessage,
        uploadFile,
        uploadImage,
        isTimelineOpen,
        isBackendReady
    ]);

    return (
        <ThreadContext.Provider value={value}>
            {children}
        </ThreadContext.Provider>
    );
};
