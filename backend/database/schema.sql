-- =====================================================
-- MAIRA PostgreSQL Schema
-- Optimized for LangGraph state persistence with user-based thread management
-- Uses UUID v7 for time-ordered, sortable identifiers
-- =====================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";  -- pgvector for embedding storage

-- =====================================================
-- UUID v7 Generation Function
-- UUID v7 is time-ordered (48-bit timestamp + random)
-- =====================================================
CREATE OR REPLACE FUNCTION generate_uuid_v7()
RETURNS UUID AS $$
DECLARE
    unix_ts_ms BIGINT;
    uuid_bytes BYTEA;
BEGIN
    unix_ts_ms := (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::BIGINT;
    
    -- Build 16 bytes: 6 bytes timestamp + 10 bytes random
    uuid_bytes := 
        -- First 6 bytes: 48-bit timestamp (big-endian)
        SET_BYTE(SET_BYTE(SET_BYTE(SET_BYTE(SET_BYTE(SET_BYTE(
            gen_random_bytes(16),
            0, (unix_ts_ms >> 40)::INT & 255),
            1, (unix_ts_ms >> 32)::INT & 255),
            2, (unix_ts_ms >> 24)::INT & 255),
            3, (unix_ts_ms >> 16)::INT & 255),
            4, (unix_ts_ms >> 8)::INT & 255),
            5, unix_ts_ms::INT & 255);
    
    -- Set version (7) in byte 6: clear top 4 bits, set to 0111
    uuid_bytes := SET_BYTE(uuid_bytes, 6, (GET_BYTE(uuid_bytes, 6) & 15) | 112);
    
    -- Set variant (10) in byte 8: clear top 2 bits, set to 10
    uuid_bytes := SET_BYTE(uuid_bytes, 8, (GET_BYTE(uuid_bytes, 8) & 63) | 128);
    
    RETURN encode(uuid_bytes, 'hex')::UUID;
END;
$$ LANGUAGE plpgsql VOLATILE;

-- =====================================================
-- 1. USERS TABLE
-- Stores user accounts for multi-user support
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT generate_uuid_v7(),
    email VARCHAR(255) UNIQUE,
    username VARCHAR(100),
    display_name VARCHAR(255),
    avatar_url TEXT,
    auth_provider VARCHAR(50) DEFAULT 'local',  -- 'local', 'google', 'github', etc.
    auth_provider_id VARCHAR(255),              -- External auth ID
    preferences JSONB DEFAULT '{}',             -- User preferences (theme, settings, etc.)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Indexes for users
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_auth_provider ON users(auth_provider, auth_provider_id);
CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active_at DESC);

-- =====================================================
-- 2. THREADS TABLE
-- Conversation threads owned by users
-- UUID v7 ensures natural time-ordering
-- =====================================================
CREATE TABLE IF NOT EXISTS threads (
    thread_id UUID PRIMARY KEY DEFAULT generate_uuid_v7(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(500) DEFAULT 'New Chat',
    
    -- Branching support
    parent_thread_id UUID REFERENCES threads(thread_id) ON DELETE SET NULL,
    fork_checkpoint_id VARCHAR(255),            -- Checkpoint ID where branch occurred
    
    -- Metadata
    message_count INTEGER DEFAULT 0,
    deep_research_enabled BOOLEAN DEFAULT FALSE,
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'active',        -- 'active', 'archived', 'deleted'
    
    -- Timestamps (UUID v7 already encodes creation time, but explicit is useful)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Soft delete support
    deleted_at TIMESTAMPTZ
);

-- Indexes for threads
CREATE INDEX IF NOT EXISTS idx_threads_user_id ON threads(user_id);
CREATE INDEX IF NOT EXISTS idx_threads_user_updated ON threads(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_threads_user_status ON threads(user_id, status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_threads_parent ON threads(parent_thread_id) WHERE parent_thread_id IS NOT NULL;

-- =====================================================
-- 3. MESSAGES TABLE
-- Stores individual messages for quick retrieval
-- Denormalized for performance (avoids parsing checkpoint blobs)
-- =====================================================
CREATE TABLE IF NOT EXISTS messages (
    message_id UUID PRIMARY KEY DEFAULT generate_uuid_v7(),
    thread_id UUID NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Message content
    role VARCHAR(50) NOT NULL,                  -- 'user', 'assistant', 'system', 'tool'
    content TEXT,
    
    -- Rich content support
    content_type VARCHAR(50) DEFAULT 'text',    -- 'text', 'markdown', 'code', 'image'
    attachments JSONB DEFAULT '[]',             -- File attachments, images, etc.
    
    -- Tool/Function call data
    tool_calls JSONB,                           -- For assistant messages with tool calls
    tool_call_id VARCHAR(255),                  -- For tool response messages
    tool_name VARCHAR(255),
    
    -- AI-specific metadata
    model_name VARCHAR(100),
    tokens_used INTEGER,
    reasoning TEXT,                             -- <think> block content
    
    -- Verification data
    verification JSONB,                         -- Verification scores, status
    
    -- Download data
    download JSONB,                             -- {filename, data, type}
    
    -- Checkpoint reference
    checkpoint_id VARCHAR(255),
    
    -- Position in thread
    sequence_number INTEGER NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for messages
CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread_sequence ON messages(thread_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_checkpoint ON messages(checkpoint_id) WHERE checkpoint_id IS NOT NULL;

-- =====================================================
-- NOTE: CHECKPOINTS & CHECKPOINT_WRITES TABLES
-- These tables are NOT created manually!
-- 
-- The AsyncPostgresSaver.setup() method from langgraph-checkpoint-postgres
-- automatically creates and manages:
--   - checkpoint_migrations
--   - checkpoints  
--   - checkpoint_blobs
--   - checkpoint_writes
--
-- This ensures compatibility with LangGraph's internal schema requirements.
-- Manually creating these tables would cause schema mismatches.
-- =====================================================

-- =====================================================
-- 4. ACTIVE_SESSIONS TABLE
-- Tracks active streaming sessions for reconnection
-- Enables resume after frontend refresh
-- =====================================================
CREATE TABLE IF NOT EXISTS active_sessions (
    session_id UUID PRIMARY KEY DEFAULT generate_uuid_v7(),
    thread_id UUID NOT NULL REFERENCES threads(thread_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Session state
    status VARCHAR(50) DEFAULT 'running',       -- 'running', 'completed', 'error', 'cancelled'
    
    -- Request context (for reconnection)
    prompt TEXT NOT NULL,
    deep_research BOOLEAN DEFAULT FALSE,
    parent_checkpoint_id VARCHAR(255),
    
    -- Progress tracking
    last_content TEXT,                          -- Last streamed content
    last_event_id VARCHAR(255),
    event_count INTEGER DEFAULT 0,
    
    -- Buffered events for reconnection (stored as JSONB array)
    events_buffer JSONB DEFAULT '[]',
    
    -- Timestamps
    started_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    
    -- TTL for cleanup (sessions older than this are expired)
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '24 hours')
);

-- Indexes for active_sessions
CREATE INDEX IF NOT EXISTS idx_sessions_thread ON active_sessions(thread_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON active_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON active_sessions(status) WHERE status = 'running';
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON active_sessions(expires_at);

-- =====================================================
-- 7. USER_SETTINGS TABLE
-- Stores user-specific settings and preferences
-- =====================================================
CREATE TABLE IF NOT EXISTS user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- AI Settings
    default_model VARCHAR(100) DEFAULT 'gemini-2.0-flash',
    deep_research_default BOOLEAN DEFAULT FALSE,
    temperature DECIMAL(3,2) DEFAULT 0.7,
    
    -- UI Settings
    theme VARCHAR(50) DEFAULT 'dark',
    sidebar_collapsed BOOLEAN DEFAULT FALSE,
    show_reasoning BOOLEAN DEFAULT TRUE,
    
    -- Notification Settings
    notifications_enabled BOOLEAN DEFAULT TRUE,
    
    -- Custom settings as JSON
    custom_settings JSONB DEFAULT '{}',
    
    -- Timestamps
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- 8. API_KEYS TABLE
-- Stores user API keys for external services
-- =====================================================
CREATE TABLE IF NOT EXISTS api_keys (
    key_id UUID PRIMARY KEY DEFAULT generate_uuid_v7(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- Key info
    key_name VARCHAR(100) NOT NULL,             -- 'openai', 'anthropic', 'google', etc.
    encrypted_key TEXT NOT NULL,                -- Encrypted API key
    
    -- Usage tracking
    last_used_at TIMESTAMPTZ,
    usage_count INTEGER DEFAULT 0,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, key_name)
);

-- Index for api_keys
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);

-- =====================================================
-- TRIGGER FUNCTIONS
-- Auto-update timestamps
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_threads_updated_at
    BEFORE UPDATE ON threads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_sessions_updated_at
    BEFORE UPDATE ON active_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trigger_user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =====================================================
-- TRIGGER: Update thread message count
-- =====================================================
CREATE OR REPLACE FUNCTION update_thread_message_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE threads SET message_count = message_count + 1 WHERE thread_id = NEW.thread_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE threads SET message_count = message_count - 1 WHERE thread_id = OLD.thread_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_message_count
    AFTER INSERT OR DELETE ON messages
    FOR EACH ROW EXECUTE FUNCTION update_thread_message_count();

-- =====================================================
-- CLEANUP FUNCTION
-- Removes expired sessions and soft-deleted threads
-- =====================================================
CREATE OR REPLACE FUNCTION cleanup_expired_data()
RETURNS void AS $$
BEGIN
    -- Remove expired sessions
    DELETE FROM active_sessions WHERE expires_at < NOW();
    
    -- Remove soft-deleted threads older than 30 days
    DELETE FROM threads 
    WHERE deleted_at IS NOT NULL 
    AND deleted_at < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VIEWS FOR COMMON QUERIES
-- =====================================================

-- User's threads with last message preview
CREATE OR REPLACE VIEW user_threads_summary AS
SELECT 
    t.thread_id,
    t.user_id,
    t.title,
    t.message_count,
    t.deep_research_enabled,
    t.status,
    t.created_at,
    t.updated_at,
    t.parent_thread_id,
    (
        SELECT m.content 
        FROM messages m 
        WHERE m.thread_id = t.thread_id 
        ORDER BY m.sequence_number DESC 
        LIMIT 1
    ) as last_message_preview
FROM threads t
WHERE t.status = 'active' AND t.deleted_at IS NULL;

-- Active running sessions
CREATE OR REPLACE VIEW running_sessions AS
SELECT 
    s.session_id,
    s.thread_id,
    s.user_id,
    s.prompt,
    s.deep_research,
    s.status,
    s.event_count,
    s.started_at,
    s.updated_at,
    t.title as thread_title
FROM active_sessions s
JOIN threads t ON s.thread_id = t.thread_id
WHERE s.status = 'running' AND s.expires_at > NOW();

-- =====================================================
-- LONG-TERM MEMORY STORE (LangGraph Store)
-- Persistent storage for agent memories across threads
-- =====================================================
-- NOTE: This table is auto-created by AsyncPostgresStore.setup()
-- but we document it here for reference and manual setup if needed.

CREATE TABLE IF NOT EXISTS store (
    prefix TEXT NOT NULL,                       -- Namespace prefix (e.g., agent memory path)
    key TEXT NOT NULL,                          -- Unique key within namespace
    value JSONB NOT NULL,                       -- Stored content
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (prefix, key)
);

-- Index for efficient namespace queries
CREATE INDEX IF NOT EXISTS idx_store_prefix ON store(prefix);
CREATE INDEX IF NOT EXISTS idx_store_updated ON store(updated_at DESC);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_store_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_store_updated_at ON store;
CREATE TRIGGER trigger_store_updated_at
    BEFORE UPDATE ON store
    FOR EACH ROW
    EXECUTE FUNCTION update_store_updated_at();

-- =====================================================
-- SAMPLE DATA (Optional - for testing)
-- =====================================================
-- INSERT INTO users (email, username, display_name) 
-- VALUES ('test@example.com', 'testuser', 'Test User');

-- =====================================================
-- CUSTOM PERSONAS TABLE
-- User-defined personas with custom instructions
-- =====================================================
CREATE TABLE IF NOT EXISTS custom_personas (
    persona_id UUID PRIMARY KEY DEFAULT generate_uuid_v7(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Persona info
    name VARCHAR(100) NOT NULL,
    instructions TEXT NOT NULL,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for custom_personas
CREATE INDEX IF NOT EXISTS idx_custom_personas_user ON custom_personas(user_id);
CREATE INDEX IF NOT EXISTS idx_custom_personas_user_active ON custom_personas(user_id) WHERE is_active = TRUE;

-- Trigger to auto-update updated_at
CREATE TRIGGER trigger_custom_personas_updated_at
    BEFORE UPDATE ON custom_personas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- =====================================================
-- USER SITES TABLE
-- Stores user-specific search sites that persist across sessions
-- =====================================================
CREATE TABLE IF NOT EXISTS user_sites (
    site_id UUID PRIMARY KEY DEFAULT generate_uuid_v7(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    -- Site URL (cleaned, e.g. "github.com")
    url VARCHAR(500) NOT NULL,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Prevent duplicate sites per user
    UNIQUE(user_id, url)
);

-- Indexes for user_sites
CREATE INDEX IF NOT EXISTS idx_user_sites_user ON user_sites(user_id);


-- =====================================================
-- GRANTS (Adjust based on your database user)
-- =====================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO maira_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO maira_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO maira_user;

