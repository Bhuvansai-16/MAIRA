"""
PostgreSQL Database Configuration (Supabase)

Handles:
- Connection pool management
- PostgresSaver checkpointer setup (short-term chat history)
- PostgresStore for long-term memory (persistent across threads)
"""

import os
import threading
import functools
import time as _time
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

# =====================================================
# SUPABASE CONNECTION CONFIG
# =====================================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_PROJECT_REF = SUPABASE_URL.replace("https://", "").replace(".supabase.co", "") if SUPABASE_URL else ""
SUPABASE_PASSWORD = os.getenv("MAIRA_PASSWORD", "")

# Construct PostgreSQL connection string for Supabase
# Production-ready: aggressive TCP keepalive, connect timeout, SSL
DB_URI = (
    f"postgresql://postgres:{SUPABASE_PASSWORD}@db.{SUPABASE_PROJECT_REF}.supabase.co:5432/postgres"
    f"?sslmode=require"
    f"&connect_timeout=10"         # Fail fast on unreachable server
    f"&keepalives=1"               # Enable TCP keepalive
    f"&keepalives_idle=20"         # Start probing after 20s idle (was 30)
    f"&keepalives_interval=5"      # Probe every 5s (was 10)
    f"&keepalives_count=3"         # Give up after 3 failed probes (was 5)
    f"&tcp_user_timeout=30000"     # 30s TCP-level timeout (ms)
)

# =====================================================
# SYNC CONNECTION POOL FOR POSTGRES (Production-Ready)
# open=False means we'll open it manually in lifespan
# =====================================================
POOL_CONFIG = dict(
    conninfo=DB_URI,
    min_size=1,
    max_size=3,             # Supabase free-tier connection limit friendly
    open=False,
    max_idle=60,            # Close idle connections after 60s (was 120)
    max_lifetime=300,       # Recycle connections every 5 min (was 10 min)
    reconnect_timeout=30,   # Wait up to 30s when reconnecting
    num_workers=2,          # Background workers for health checks
    check=ConnectionPool.check_connection,  # Validate before handing out
)

pool = ConnectionPool(**POOL_CONFIG)

# Dedicated pool for PostgresSaver / PostgresStore — NEVER reset during streaming.
# This prevents the "pool is already closed" crash when reset_pool() is called
# while the agent is still saving checkpoints in a background thread.
CHECKPOINTER_POOL_CONFIG = dict(
    conninfo=DB_URI,
    min_size=1,
    max_size=2,             # Checkpointer needs fewer connections
    open=False,
    max_idle=60,
    max_lifetime=300,
    reconnect_timeout=30,
    num_workers=2,
    check=ConnectionPool.check_connection,
)

_checkpointer_pool = ConnectionPool(**CHECKPOINTER_POOL_CONFIG)

# Thread safety for pool reset operations
_pool_lock = threading.Lock()

# Fallback checkpointer for when PostgreSQL fails
_fallback_checkpointer = None


# =====================================================
# POOL MANAGEMENT & RETRY INFRASTRUCTURE
# (must be defined before functions that use @with_db_retry)
# =====================================================

def open_all_pools():
    """
    Open both the CRUD pool and the checkpointer pool.
    Call once at startup (from main_agent.py).
    """
    pool.open()
    _checkpointer_pool.open()
    print("✅ All PostgreSQL connection pools opened")


def reset_pool():
    """
    Thread-safe CRUD pool reset to recover from SSL/connection errors.
    Only resets the CRUD pool — the checkpointer pool is left intact
    so active LangGraph background threads can still save state.
    """
    global pool
    with _pool_lock:
        old_pool = pool
        try:
            old_pool.close(timeout=5)
        except Exception:
            pass
        
        pool = ConnectionPool(**POOL_CONFIG)
        pool.open()
        print("🔄 CRUD connection pool reset successfully")


def validate_pool() -> bool:
    """
    Quick health check: can we execute a query on the pool?
    Returns True if healthy, False otherwise.
    """
    try:
        with pool.connection(timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"⚠️ Pool validation failed: {e}")
        return False


def ensure_healthy_pool():
    """
    Validate the pool and reset it if unhealthy.
    Raises RuntimeError if recovery fails.
    """
    if not validate_pool():
        print("🔄 Pool unhealthy, resetting...")
        reset_pool()
        if not validate_pool():
            raise RuntimeError("Failed to restore database connection after pool reset")
        print("✅ Pool recovered after reset")


def _is_transient_error(error_msg: str) -> bool:
    """Check if an error message indicates a transient DB/SSL failure."""
    markers = [
        "ssl", "bad length", "eof detected",
        "server closed", "broken pipe", "connection reset",
        "no connection", "could not connect", "connection refused",
        "connection timed out", "network", "timeout",
        "operational error", "interface error",
    ]
    lower = error_msg.lower()
    return any(m in lower for m in markers)


def with_db_retry(max_retries: int = 2, base_delay: float = 0.5):
    """
    Decorator that retries a function on transient DB errors with
    exponential backoff and automatic pool recovery.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if _is_transient_error(str(e)) and attempt < max_retries:
                        wait = base_delay * (2 ** attempt)
                        print(f"⚠️ DB retry {attempt + 1}/{max_retries} for {func.__name__}: {e}")
                        _time.sleep(wait)
                        try:
                            ensure_healthy_pool()
                        except Exception:
                            pass
                        continue
                    raise
            raise last_error  # Should not reach here, but safety net
        return wrapper
    return decorator


# =====================================================
# CHECKPOINTER & STORE
# =====================================================

@with_db_retry(max_retries=3, base_delay=1.0)
def get_checkpointer() -> PostgresSaver:
    """
    Returns a ready-to-use sync checkpointer backed by its own dedicated pool.
    This pool is never reset during streaming, so background threads can
    always save checkpoints safely.
    
    setup() is idempotent - safe to call on every initialization.
    Falls back to MemorySaver if PostgreSQL connection fails.
    """
    global _fallback_checkpointer
    
    try:
        # Test the checkpointer pool health
        with _checkpointer_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        
        checkpointer = PostgresSaver(_checkpointer_pool)
        checkpointer.setup()
        print("✅ PostgresSaver checkpointer ready (dedicated pool)")
        return checkpointer
    except Exception as e:
        print(f"⚠️ PostgreSQL checkpointer failed: {e}")
        print("   Falling back to in-memory checkpointer (state won't persist across restarts)")
        if _fallback_checkpointer is None:
            _fallback_checkpointer = MemorySaver()
        return _fallback_checkpointer


@with_db_retry(max_retries=2)
def get_store():
    """
    Returns a persistent store for long-term memory.
    Uses the dedicated checkpointer pool (never reset during streaming).
    
    This store persists data across:
    - Multiple conversation threads
    - Server restarts
    - Different user sessions
    
    The table schema will be auto-fixed on startup if columns are missing.
    """
    from langgraph.store.postgres import PostgresStore
    store = PostgresStore(_checkpointer_pool)
    
    # Auto-fix store table schema - add missing columns if needed
    try:
        with _checkpointer_pool.connection() as conn:
            with conn.cursor() as cur:
                # Add ttl_minutes column if missing
                cur.execute("""
                    ALTER TABLE public.store 
                    ADD COLUMN IF NOT EXISTS ttl_minutes INTEGER DEFAULT NULL
                """)
                
                # Add expires_at column if missing
                cur.execute("""
                    ALTER TABLE public.store 
                    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ DEFAULT NULL
                """)
                
                # Add namespace column if missing (sometimes used instead of prefix)
                cur.execute("""
                    ALTER TABLE public.store 
                    ADD COLUMN IF NOT EXISTS namespace TEXT DEFAULT ''
                """)
                
                conn.commit()
                print("✅ Store table schema verified/updated with all required columns")
    except Exception as e:
        print(f"⚠️ Could not update store table schema: {e}")
        print("   The agent will still work but long-term memory may be limited")
    
    return store


# =====================================================
# USER & THREAD MANAGEMENT FUNCTIONS
# =====================================================

@with_db_retry()
def get_user_by_id(user_id: str) -> dict | None:
    """
    Get a user by their ID from the users table.
    Returns None if user doesn't exist.
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, email, display_name, avatar_url, auth_provider, 
                           created_at, updated_at, last_active_at, is_active
                    FROM users 
                    WHERE user_id = %s::uuid AND is_active = true
                    """,
                    (user_id,)
                )
                row = cur.fetchone()
                if row:
                    return {
                        "user_id": str(row[0]),
                        "email": row[1],
                        "display_name": row[2],
                        "avatar_url": row[3],
                        "auth_provider": row[4],
                        "created_at": row[5].isoformat() if row[5] else None,
                        "updated_at": row[6].isoformat() if row[6] else None,
                        "last_active_at": row[7].isoformat() if row[7] else None,
                        "is_active": row[8]
                    }
                return None
    except Exception as e:
        print(f"⚠️ Error fetching user {user_id}: {e}")
        return None


@with_db_retry()
def user_exists(user_id: str) -> bool:
    """Check if a user exists in the database."""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM users WHERE user_id = %s::uuid AND is_active = true",
                    (user_id,)
                )
                return cur.fetchone() is not None
    except Exception as e:
        print(f"⚠️ Error checking user existence: {e}")
        return False


@with_db_retry()
def sync_user(user_id: str, email: str = None, display_name: str = None, 
              avatar_url: str = None, auth_provider: str = "email") -> dict | None:
    """
    Create or update a user in the users table.
    Used when syncing from Supabase Auth.
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (user_id, email, display_name, avatar_url, auth_provider, auth_provider_id, updated_at, last_active_at)
                    VALUES (%s::uuid, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (user_id) DO UPDATE SET
                        email = COALESCE(EXCLUDED.email, users.email),
                        display_name = COALESCE(EXCLUDED.display_name, users.display_name),
                        avatar_url = COALESCE(EXCLUDED.avatar_url, users.avatar_url),
                        updated_at = NOW(),
                        last_active_at = NOW()
                    RETURNING user_id, email, display_name
                    """,
                    (user_id, email, display_name, avatar_url, auth_provider, user_id)
                )
                row = cur.fetchone()
                conn.commit()
                
                if row:
                    print(f"✅ User {user_id} synced to database")
                    return {
                        "user_id": str(row[0]),
                        "email": row[1],
                        "display_name": row[2]
                    }
                return None
    except Exception as e:
        print(f"⚠️ Error syncing user: {e}")
        return None


@with_db_retry()
def get_threads_by_user(user_id: str) -> list[dict]:
    """
    Get all threads belonging to a specific user.
    Returns threads sorted by updated_at (newest first).
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT thread_id, title, message_count, deep_research_enabled, 
                           status, created_at, updated_at
                    FROM threads 
                    WHERE user_id = %s::uuid 
                      AND status = 'active' 
                      AND deleted_at IS NULL
                    ORDER BY updated_at DESC
                    """,
                    (user_id,)
                )
                rows = cur.fetchall()
                threads = []
                for row in rows:
                    threads.append({
                        "thread_id": str(row[0]),
                        "title": row[1] or "New Chat",
                        "message_count": row[2] or 0,
                        "deep_research_enabled": row[3] or False,
                        "status": row[4] or "active",
                        "created_at": row[5].isoformat() if row[5] else None,
                        "updated_at": row[6].isoformat() if row[6] else None
                    })
                print(f"📋 Found {len(threads)} threads for user {user_id}")
                return threads
    except Exception as e:
        print(f"⚠️ Error fetching threads for user {user_id}: {e}")
        return []


@with_db_retry()
def create_thread_for_user(thread_id: str, user_id: str, title: str = "New Chat") -> dict | None:
    """
    Create a new thread for a specific user.
    Validates that the user exists before creating.
    """
    if not user_exists(user_id):
        print(f"⚠️ Cannot create thread: user {user_id} does not exist")
        return None
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO threads (thread_id, user_id, title, created_at, updated_at)
                    VALUES (%s::uuid, %s::uuid, %s, NOW(), NOW())
                    ON CONFLICT (thread_id) DO UPDATE SET 
                        title = EXCLUDED.title, 
                        updated_at = NOW()
                    RETURNING thread_id, title, created_at, updated_at
                    """,
                    (thread_id, user_id, title)
                )
                row = cur.fetchone()
                conn.commit()
                
                if row:
                    print(f"✅ Thread {thread_id} created for user {user_id}")
                    return {
                        "thread_id": str(row[0]),
                        "title": row[1],
                        "created_at": row[2].isoformat() if row[2] else None,
                        "updated_at": row[3].isoformat() if row[3] else None
                    }
                return None
    except Exception as e:
        print(f"⚠️ Error creating thread: {e}")
        return None


@with_db_retry()
def get_thread_by_id(thread_id: str, user_id: str = None) -> dict | None:
    """
    Get a specific thread by ID.
    If user_id is provided, also validates ownership.
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                if user_id:
                    # Validate ownership
                    cur.execute(
                        """
                        SELECT thread_id, user_id, title, message_count, deep_research_enabled, 
                               status, created_at, updated_at
                        FROM threads 
                        WHERE thread_id = %s::uuid 
                          AND user_id = %s::uuid
                          AND status = 'active' 
                          AND deleted_at IS NULL
                        """,
                        (thread_id, user_id)
                    )
                else:
                    cur.execute(
                        """
                        SELECT thread_id, user_id, title, message_count, deep_research_enabled, 
                               status, created_at, updated_at
                        FROM threads 
                        WHERE thread_id = %s::uuid 
                          AND status = 'active' 
                          AND deleted_at IS NULL
                        """,
                        (thread_id,)
                    )
                
                row = cur.fetchone()
                if row:
                    return {
                        "thread_id": str(row[0]),
                        "user_id": str(row[1]),
                        "title": row[2] or "New Chat",
                        "message_count": row[3] or 0,
                        "deep_research_enabled": row[4] or False,
                        "status": row[5] or "active",
                        "created_at": row[6].isoformat() if row[6] else None,
                        "updated_at": row[7].isoformat() if row[7] else None
                    }
                return None
    except Exception as e:
        print(f"⚠️ Error fetching thread {thread_id}: {e}")
        return None


@with_db_retry()
def update_thread_title(thread_id: str, title: str, user_id: str = None) -> bool:
    """
    Update a thread's title.
    If user_id is provided, validates ownership.
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute(
                        """
                        UPDATE threads 
                        SET title = %s, updated_at = NOW() 
                        WHERE thread_id = %s::uuid 
                          AND user_id = %s::uuid
                          AND status = 'active'
                        RETURNING thread_id
                        """,
                        (title, thread_id, user_id)
                    )
                else:
                    cur.execute(
                        """
                        UPDATE threads 
                        SET title = %s, updated_at = NOW() 
                        WHERE thread_id = %s::uuid 
                          AND status = 'active'
                        RETURNING thread_id
                        """,
                        (title, thread_id)
                    )
                
                result = cur.fetchone()
                conn.commit()
                return result is not None
    except Exception as e:
        print(f"⚠️ Error updating thread title: {e}")
        return False


@with_db_retry()
def delete_thread(thread_id: str, user_id: str = None) -> bool:
    """
    Soft delete a thread (sets deleted_at and status).
    If user_id is provided, validates ownership.
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute(
                        """
                        UPDATE threads 
                        SET status = 'deleted', deleted_at = NOW(), updated_at = NOW()
                        WHERE thread_id = %s::uuid 
                          AND user_id = %s::uuid
                          AND status = 'active'
                        RETURNING thread_id
                        """,
                        (thread_id, user_id)
                    )
                else:
                    cur.execute(
                        """
                        UPDATE threads 
                        SET status = 'deleted', deleted_at = NOW(), updated_at = NOW()
                        WHERE thread_id = %s::uuid 
                          AND status = 'active'
                        RETURNING thread_id
                        """,
                        (thread_id,)
                    )
                
                result = cur.fetchone()
                conn.commit()
                
                if result:
                    print(f"🗑️ Thread {thread_id} deleted")
                    return True
                return False
    except Exception as e:
        print(f"⚠️ Error deleting thread: {e}")
        return False
