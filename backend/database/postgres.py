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
import json
import time as _time
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver
from psycopg.rows import dict_row

load_dotenv()

try:
    from ..redis_client import redis_client
except ImportError:
    # Handle direct execution or different path structure
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from redis_client import redis_client

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
    f"&keepalives_idle=10"         # Start probing after 10s idle (was 20)
    f"&keepalives_interval=3"      # Probe every 3s (was 5)
    f"&keepalives_count=5"         # Give up after 5 failed probes (was 3)
    f"&tcp_user_timeout=30000"     # 30s TCP-level timeout (ms)
)

# =====================================================
# SYNC CONNECTION POOL FOR POSTGRES (Production-Ready)
# open=False means we'll open it manually in lifespan
# =====================================================
POOL_CONFIG = dict(
    conninfo=DB_URI,
    min_size=2,          # Increased from 1
    max_size=15,         # INCREASED from 2
    open=False,
    max_idle=45,            # Close idle connections after 45s (was 60)
    max_lifetime=240,       # Recycle every 4 min (was 5 min)
    reconnect_timeout=30,
    num_workers=2,
    check=ConnectionPool.check_connection,
)

pool = ConnectionPool(**POOL_CONFIG)

# Dedicated pool for PostgresSaver / PostgresStore — NEVER reset during streaming.
# This prevents the "pool is already closed" crash when reset_pool() is called
# while the agent is still saving checkpoints in a background thread.
# Connection budget: CRUD pool (2) + Checkpointer pool (2) + PGVector (1) = 5 total
# Well within Supabase free-tier ~20 connection limit
CHECKPOINTER_POOL_CONFIG = dict(
    conninfo=DB_URI,
    min_size=2,          # Increased from 1
    max_size=15,         # INCREASED from 2
    open=False,
    max_idle=15,            # Close idle after 15s — faster SSL recycle
    max_lifetime=90,        # Recycle every 90s — prevent stale SSL sessions
    reconnect_timeout=20,   # Faster reconnect timeout
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
    """ Open both pools. Safe to call multiple times. """
    if pool.closed:
        pool.open()
    if _checkpointer_pool.closed:
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


def reset_checkpointer_pool():
    """
    Reset the checkpointer pool to recover from SSL errors.
    Called during stream retry when the checkpoint save fails.
    """
    global _checkpointer_pool
    with _pool_lock:
        old_pool = _checkpointer_pool
        try:
            old_pool.close(timeout=3)  # Faster timeout
        except Exception:
            pass
        
        _checkpointer_pool = ConnectionPool(**CHECKPOINTER_POOL_CONFIG)
        _checkpointer_pool.open()
        
        # Warm up the pool with a test query to establish fresh SSL connection
        try:
            with _checkpointer_pool.connection(timeout=5) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            print("🔄 Checkpointer pool reset and warmed up successfully")
        except Exception as e:
            print(f"🔄 Checkpointer pool reset (warmup failed: {e})")


def validate_pool() -> bool:
    """
    Quick health check: can we execute a query on the pool?
    Returns True if healthy, False otherwise.
    """
    try:
        if pool.closed:
            print("⚠️ Health check: CRUD pool is closed, resetting...")
            reset_pool()
            return False
        with pool.connection(timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"⚠️ Pool validation failed: {e}")
        return False


def validate_checkpointer_pool() -> bool:
    """Health check for the checkpointer pool."""
    global _checkpointer_pool
    try:
        if _checkpointer_pool.closed:
            print("⚠️ Health check: checkpointer pool is closed, resetting...")
            reset_checkpointer_pool()
            return False
        with _checkpointer_pool.connection(timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"⚠️ Health check: checkpointer pool failed: {e}")
        # Auto-recover instead of just reporting
        try:
            reset_checkpointer_pool()
            print("✅ Checkpointer pool auto-recovered")
        except Exception as re:
            print(f"❌ Checkpointer pool recovery failed: {re}")
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
        # SSL-specific errors
        "ssl", "bad length", "eof detected", "ssl_read", "ssl_write",
        "sslv3 alert", "tls", "certificate", "handshake",
        # Connection errors
        "server closed", "broken pipe", "connection reset",
        "no connection", "could not connect", "connection refused",
        "connection timed out", "network", "timeout",
        "connection unexpectedly closed", "server unexpectedly closed",
        # Pool errors
        "pool is closed", "pool exhausted", "connection is closed",
        "cannot allocate", "pool timeout",
        # psycopg/database errors
        "operational error", "interface error", "database error",
        "query was cancelled", "terminating connection",
        "the connection is closed", "connection has been closed",
        # Supabase-specific
        "pgbouncer", "too many connections", "max_connections",
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

def get_checkpointer() -> PostgresSaver:
    """
    Always return a fresh PostgresSaver bound to the CURRENT _checkpointer_pool.
    Never cache this — pools can be reset at any time.
    """
    global _checkpointer_pool, _fallback_checkpointer
    
    if _checkpointer_pool.closed:
        print("⚠️ Checkpointer pool was closed, reopening...")
        reset_checkpointer_pool()
        
    try:
        saver = PostgresSaver(_checkpointer_pool)
        saver.setup()
        # print("✅ PostgresSaver checkpointer ready (dedicated pool)")
        return saver
    except Exception as e:
        print(f"⚠️ PostgresSaver init failed, falling back to MemorySaver: {e}")
        if _fallback_checkpointer is None:
            _fallback_checkpointer = MemorySaver()
        return _fallback_checkpointer


@with_db_retry(max_retries=2)
def get_store():
    """
    Returns a persistent store for long-term memory.
    Uses the dedicated checkpointer pool (never reset during streaming).
    """
    global _checkpointer_pool
    
    # Ensure pool is open
    if _checkpointer_pool.closed:
        print("⚠️ Store pool was closed, reopening...")
        reset_checkpointer_pool()
        
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


# =====================================================
# CUSTOM PERSONAS MANAGEMENT
# =====================================================

@with_db_retry()
def create_custom_persona(user_id: str, name: str, instructions: str) -> dict | None:
    """
    Create a new custom persona for a user.
    Returns the created persona dict or None on failure.
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO custom_personas (persona_id, user_id, name, instructions)
                    VALUES (gen_random_uuid(), %s::uuid, %s, %s)
                    RETURNING persona_id, name, instructions, created_at
                    """,
                    (user_id, name, instructions)
                )
                row = cur.fetchone()
                conn.commit()

                if row:
                    print(f"✅ Custom persona '{name}' created for user {user_id}")
                    return {
                        "persona_id": str(row[0]),
                        "name": row[1],
                        "instructions": row[2],
                        "created_at": row[3].isoformat() if row[3] else None
                    }
                return None
    except Exception as e:
        print(f"⚠️ Error creating custom persona: {e}")
        return None
    finally:
        # Invalidate cache safely
        if redis_client:
            try:
                redis_client.delete(f"personas:{user_id}")
            except Exception as e:
                print(f"⚠️ Cache invalidation failed: {e}")


@with_db_retry()
def get_custom_personas(user_id: str) -> list[dict]:
    """
    Get all active custom personas for a user.
    Returns list of persona dicts sorted by creation time.
    """
    # 1. Check Redis cache
    cache_key = f"personas:{user_id}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                print(f"⚡ Cache HIT for personas: {user_id}")
                return json.loads(cached)
        except Exception as e:
            print(f"⚠️ Redis persona cache error: {e}")

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT persona_id, name, instructions, created_at
                    FROM custom_personas
                    WHERE user_id = %s::uuid AND is_active = TRUE
                    ORDER BY created_at ASC
                    """,
                    (user_id,)
                )
                rows = cur.fetchall()
                personas = []
                for row in rows:
                    personas.append({
                        "persona_id": str(row[0]),
                        "name": row[1],
                        "instructions": row[2],
                        "created_at": row[3].isoformat() if row[3] else None
                    })
                print(f"👤 Found {len(personas)} custom personas for user {user_id}")
                
                # 2. Cache results
                if redis_client:
                    try:
                        redis_client.setex(cache_key, 3600, json.dumps(personas))
                    except Exception as e:
                        print(f"⚠️ Failed to cache personas: {e}")
                
                return personas
    except Exception as e:
        print(f"⚠️ Error fetching custom personas: {e}")
        return []


@with_db_retry()
def update_custom_persona(persona_id: str, user_id: str, name: str = None, instructions: str = None) -> bool:
    """
    Update a custom persona's name and/or instructions.
    Validates ownership via user_id.
    """
    try:
        updates = []
        params = []
        if name is not None:
            updates.append("name = %s")
            params.append(name)
        if instructions is not None:
            updates.append("instructions = %s")
            params.append(instructions)
        
        if not updates:
            return False
        
        params.extend([persona_id, user_id])
        
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE custom_personas
                    SET {', '.join(updates)}, updated_at = NOW()
                    WHERE persona_id = %s::uuid AND user_id = %s::uuid AND is_active = TRUE
                    RETURNING persona_id
                    """,
                    params
                )
                result = cur.fetchone()
                conn.commit()
                return result is not None
    except Exception as e:
        print(f"⚠️ Error updating custom persona: {e}")
        return False
    finally:
        # Invalidate cache safely
        if redis_client:
            try:
                redis_client.delete(f"personas:{user_id}")
            except Exception as e:
                print(f"⚠️ Cache invalidation failed: {e}")


@with_db_retry()
def delete_custom_persona(persona_id: str, user_id: str) -> bool:
    """
    Soft-delete a custom persona (set is_active = FALSE).
    Validates ownership via user_id.
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE custom_personas
                    SET is_active = FALSE, updated_at = NOW()
                    WHERE persona_id = %s::uuid AND user_id = %s::uuid AND is_active = TRUE
                    RETURNING persona_id
                    """,
                    (persona_id, user_id)
                )
                result = cur.fetchone()
                conn.commit()
                if result:
                    print(f"🗑️ Custom persona {persona_id} deleted for user {user_id}")
                    return True
                return False
    except Exception as e:
        print(f"⚠️ Error deleting custom persona: {e}")
        return False
    finally:
        # Invalidate cache safely
        if redis_client:
            try:
                redis_client.delete(f"personas:{user_id}")
            except Exception as e:
                print(f"⚠️ Cache invalidation failed: {e}")


# =====================================================
# USER SITES MANAGEMENT
# =====================================================

@with_db_retry()
def get_user_sites(user_id: str) -> list[str]:
    """
    Get all saved sites for a user.
    Returns a list of URL strings.
    """
    # 1. Check Redis cache
    cache_key = f"sites:{user_id}"
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                print(f"⚡ Cache HIT for sites: {user_id}")
                return json.loads(cached)
        except Exception as e:
            print(f"⚠️ Redis sites cache error: {e}")

    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT url FROM user_sites
                    WHERE user_id = %s::uuid
                    ORDER BY created_at ASC
                    """,
                    (user_id,)
                )
                rows = cur.fetchall()
                sites = [row[0] for row in rows]
                print(f"🌐 Found {len(sites)} saved sites for user {user_id}")
                
                # 2. Cache results
                if redis_client:
                    try:
                        redis_client.setex(cache_key, 3600, json.dumps(sites))
                    except Exception as e:
                        print(f"⚠️ Failed to cache sites: {e}")
                
                return sites
    except Exception as e:
        print(f"⚠️ Error fetching user sites: {e}")
        return []


@with_db_retry()
def set_user_sites(user_id: str, urls: list[str]) -> bool:
    """
    Replace all saved sites for a user with the given list.
    Deletes existing sites and inserts the new ones.
    """
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Delete existing sites
                cur.execute(
                    "DELETE FROM user_sites WHERE user_id = %s::uuid",
                    (user_id,)
                )
                # Insert new ones
                if urls:
                    values = [(user_id, url) for url in urls]
                    cur.executemany(
                        """
                        INSERT INTO user_sites (site_id, user_id, url)
                        VALUES (gen_random_uuid(), %s::uuid, %s)
                        ON CONFLICT (user_id, url) DO NOTHING
                        """,
                        values
                    )
                conn.commit()
                print(f"🌐 Saved {len(urls)} sites for user {user_id}")
                return True
    except Exception as e:
        print(f"⚠️ Error saving user sites: {e}")
        return False
    finally:
        # Invalidate cache safely
        if redis_client:
            try:
                redis_client.delete(f"sites:{user_id}")
            except Exception as e:
                print(f"⚠️ Cache invalidation failed: {e}")


@with_db_retry()
def add_user_site(user_id: str, url: str) -> bool:
    """Add a single site for a user."""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_sites (site_id, user_id, url)
                    VALUES (gen_random_uuid(), %s::uuid, %s)
                    ON CONFLICT (user_id, url) DO NOTHING
                    RETURNING site_id
                    """,
                    (user_id, url)
                )
                result = cur.fetchone()
                conn.commit()
                return result is not None
    except Exception as e:
        print(f"⚠️ Error adding user site: {e}")
        return False
    finally:
        # Invalidate cache safely
        if redis_client:
            try:
                redis_client.delete(f"sites:{user_id}")
            except Exception as e:
                print(f"⚠️ Cache invalidation failed: {e}")


@with_db_retry()
def remove_user_site(user_id: str, url: str) -> bool:
    """Remove a single site for a user."""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM user_sites
                    WHERE user_id = %s::uuid AND url = %s
                    RETURNING site_id
                    """,
                    (user_id, url)
                )
                result = cur.fetchone()
                conn.commit()
                return result is not None
    except Exception as e:
        print(f"⚠️ Error removing user site: {e}")
        return False
    finally:
        # Invalidate cache safely
        if redis_client:
            try:
                redis_client.delete(f"sites:{user_id}")
            except Exception as e:
                print(f"⚠️ Cache invalidation failed: {e}")

