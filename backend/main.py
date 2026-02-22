# Backend for MAIRA Deep Research Agent
# Production-ready synchronous version
# Version: 2.0.0

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from main_agent import get_agent, prompt_v2, subagents, tools
from deepagents import create_deep_agent
import database as _db
from database import (
    pool, 
    reset_pool,
    validate_pool,
    validate_checkpointer_pool,
    ensure_healthy_pool,
    _is_transient_error,
    get_user_by_id,
    user_exists,
    sync_user,
    get_threads_by_user,
    create_thread_for_user,
    get_thread_by_id,
    update_thread_title as db_update_thread_title,
    delete_thread as db_delete_thread,
    ingest_pdf,
    ingest_text,
    ingest_image_description,
    delete_user_documents,
    # Custom personas
    create_custom_persona,
    get_custom_personas,
    update_custom_persona,
    delete_custom_persona,
    # User sites
    get_user_sites,
    set_user_sites,
    add_user_site,
    remove_user_site,
)
from config import AVAILABLE_MODELS, get_current_model_info, set_current_model, get_model_instance
import config
from thread_manager import thread_manager, Thread, CheckpointInfo
from datetime import datetime, timedelta
import json
import uuid
from collections import defaultdict
import threading
import queue
import time
import download_store
import logging
import traceback

# =====================================================
# PRODUCTION CONFIGURATION
# =====================================================

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Session cleanup configuration
SESSION_TIMEOUT_MINUTES = 60  # Clean up sessions older than this
SESSION_CLEANUP_INTERVAL = 300  # Run cleanup every 5 minutes

# Request limits
MAX_PROMPT_LENGTH = 50000  # Maximum characters in a prompt
MAX_SITES_COUNT = 20  # Maximum number of site restrictions

# Active session tracking for reconnection support
# Stores: thread_id -> {"status": "running"|"completed"|"error", "events": [], "last_content": str, "prompt": str}
try:
    from redis_client import redis_client
except ImportError:
    redis_client = None

import json
from datetime import datetime

# Global state - Fallback if Redis is not available
active_sessions: Dict[str, Dict[str, Any]] = {}
session_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)

# Message queues for real-time streaming to connected clients
# thread_id -> queue.Queue
message_queues: Dict[str, queue.Queue] = {}

# Background thread references
background_threads: Dict[str, threading.Thread] = {}

# Per-thread cancellation events — set when /cancel is called
# Using threading.Event gives O(1) signalling that is safe across threads
cancellation_events: Dict[str, threading.Event] = {}

# =====================================================
# AGENT CACHING & REFRESH (Fix 2)
# =====================================================
_agent_instance = None
_agent_lock = threading.Lock()

def get_or_refresh_agent(force_refresh: bool = False):
    """
    Get or refresh the main agent instance.
    Ensures the agent always uses the latest connection pools.
    """
    global _agent_instance
    with _agent_lock:
        if _agent_instance is None or force_refresh:
            if force_refresh:
                print("🔄 Refreshing agent instance (stale pool or manual refresh)")
            _agent_instance = get_agent()
    return _agent_instance

# =====================================================
# REDIS SESSION HELPERS
# =====================================================

def init_session(thread_id: str, data: dict):
    """Initialize a session in Redis AND local memory (dual-write for reconnect support)"""
    # Always populate in-memory for reconnect stream endpoints
    active_sessions[thread_id] = data
    
    if redis_client:
        try:
            # Separate events and metadata
            mapping = {k: v for k, v in data.items() if k != "events"}
            # Serialize complex types
            serialized_mapping = {}
            for k, v in mapping.items():
                if isinstance(v, (list, dict, bool)):
                    serialized_mapping[k] = json.dumps(v)
                elif v is None:
                    serialized_mapping[k] = ""
                else:
                    serialized_mapping[k] = str(v)
            
            key = f"session:{thread_id}"
            pipeline = redis_client.pipeline()
            pipeline.delete(key)
            pipeline.delete(f"{key}:events")
            if serialized_mapping:
                pipeline.hset(key, values=serialized_mapping)
            # Set TTL (24 hours)
            pipeline.expire(key, 86400)
            pipeline.exec()
        except Exception as e:
            print(f"⚠️ Redis init_session failed: {e}")

def append_event(thread_id: str, event: dict):
    """Append event to session history (dual-write: in-memory + Redis)"""
    # Always update in-memory for reconnect stream endpoints
    if thread_id in active_sessions:
        active_sessions[thread_id]["events"].append(event)
        if event.get("messages"):
            for msg in event["messages"]:
                if msg.get("content"):
                    active_sessions[thread_id]["last_content"] = msg["content"]
    
    if redis_client:
        try:
            key = f"session:{thread_id}"
            pipeline = redis_client.pipeline()
            pipeline.rpush(f"{key}:events", json.dumps(event))
            pipeline.expire(f"{key}:events", 86400) # Refresh TTL
            
            # Update last_content if present
            if event.get("messages"):
                for msg in event["messages"]:
                    if msg.get("content"):
                         pipeline.hset(key, values={"last_content": msg["content"]})
            pipeline.exec()
        except Exception as e:
            print(f"⚠️ Redis append_event failed: {e}")

def update_session_status(thread_id: str, status: str, extra_updates: dict = None):
    """Update session status and other fields (dual-write: in-memory + Redis)"""
    # Always update in-memory for reconnect stream endpoints
    if thread_id in active_sessions:
        active_sessions[thread_id]["status"] = status
        if extra_updates:
            active_sessions[thread_id].update(extra_updates)
    
    if redis_client:
        try:
            updates = {"status": status}
            if extra_updates:
                for k, v in extra_updates.items():
                    if isinstance(v, (list, dict, bool)):
                        updates[k] = json.dumps(v)
                    elif v is None:
                        updates[k] = ""
                    else:
                        updates[k] = str(v)
            
            redis_client.hset(f"session:{thread_id}", values=updates)
        except Exception as e:
             print(f"⚠️ Redis update_session_status failed: {e}")

def get_session_status(thread_id: str):
    """Get session status"""
    if redis_client:
        try:
            return redis_client.hget(f"session:{thread_id}", "status")
        except Exception:
            pass
    
    return active_sessions.get(thread_id, {}).get("status")

# Last cleanup timestamp
_last_session_cleanup = time.time()

app = FastAPI(
    title="MAIRA – Deep Research Agent",
    version="2.0.0",
    description="Production-ready AI research assistant with deep search capabilities"
)


# =====================================================
# SESSION CLEANUP (Production Memory Management)
# =====================================================

def get_session_metadata(thread_id: str):
    """Get full session metadata"""
    if redis_client:
        try:
            data = redis_client.hgetall(f"session:{thread_id}")
            if data:
                return data
        except Exception:
            pass
    return active_sessions.get(thread_id)

def cleanup_old_sessions():
    """Remove completed/errored sessions and queues."""
    global _last_session_cleanup
    
    current_time = time.time()
    if current_time - _last_session_cleanup < SESSION_CLEANUP_INTERVAL:
        return  # Not time yet
    
    _last_session_cleanup = current_time
    cutoff = datetime.now() - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    
    # 1. Clean up fallback active_sessions
    sessions_to_remove = []
    for thread_id, session in list(active_sessions.items()):
        if session.get("status") in ("completed", "error", "cancelled"):
            started_at = session.get("started_at")
            if started_at:
                try:
                    session_time = datetime.fromisoformat(started_at)
                    if session_time < cutoff:
                        sessions_to_remove.append(thread_id)
                except (ValueError, TypeError):
                    sessions_to_remove.append(thread_id)
    
    for thread_id in sessions_to_remove:
        active_sessions.pop(thread_id, None)
        message_queues.pop(thread_id, None)
        background_threads.pop(thread_id, None)

    # 2. Clean up message_queues for Redis-managed sessions
    # (If thread_id is not in active_sessions, it's likely Redis-only)
    if redis_client:
        for thread_id in list(message_queues.keys()):
            if thread_id in active_sessions:
                continue

            # Check Redis status
            meta = get_session_metadata(thread_id)
            if not meta:
                # Session expired/gone from Redis
                message_queues.pop(thread_id, None)
                background_threads.pop(thread_id, None)
                continue
            
            # Check status and time
            status = meta.get("status")
            started_at = meta.get("started_at")
            
            should_remove = False
            if status in ("completed", "error", "cancelled"):
                if started_at:
                    try:
                        session_time = datetime.fromisoformat(started_at)
                        if session_time < cutoff:
                            should_remove = True
                    except (ValueError, TypeError):
                         should_remove = True # Bad data
                else:
                    should_remove = True # No start time
            
            if should_remove:
                message_queues.pop(thread_id, None)
                background_threads.pop(thread_id, None)
                # We don't delete from Redis here, relying on TTL (24h) 
                # or we could explicitly delete if we want stricter cleanup.
    
    if sessions_to_remove:
        logger.info(f"🧹 Cleaned up {len(sessions_to_remove)} old sessions")

# Apply lifespan manually using startup/shutdown events
@app.on_event("startup")
def startup_event():
    # 1. Pool is already opened in main_agent.py
    
    # 2. Validate CRUD pool health on startup
    if not validate_pool():
        print("⚠️ CRUD pool unhealthy on startup, resetting...")
        reset_pool()
    
    # 3. Validate checkpointer pool health on startup
    try:
        import database as _db
        with _db._checkpointer_pool.connection(timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        print("✅ Checkpointer pool healthy")
    except Exception as e:
        print(f"⚠️ Checkpointer pool unhealthy on startup: {e}")
        try:
            _db.reset_checkpointer_pool()
            print("✅ Checkpointer pool reset on startup")
        except Exception as reset_err:
            print(f"⚠️ Could not reset checkpointer pool: {reset_err}")
    
    # 4. Ensure default user exists (required for thread foreign key)
    try:
        with _db.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (user_id, email, username, display_name)
                    VALUES ('00000000-0000-0000-0000-000000000001'::uuid, 'default@maira.ai', 'default', 'Default User')
                    ON CONFLICT (user_id) DO NOTHING
                    """
                )
            conn.commit()
        print("✅ Default user verified/created")
    except Exception as e:
        print(f"⚠️ Could not verify default user: {e}")
    
    print("✅ MAIRA Agent ready")


_shutting_down = False  # Flag for background threads to detect server shutdown

@app.on_event("shutdown")
def shutdown_event():
    global _shutting_down
    _shutting_down = True
    
    # Give active background threads a chance to finish gracefully
    active_threads = {tid: t for tid, t in background_threads.items() if t.is_alive()}
    if active_threads:
        print(f"⏳ Waiting for {len(active_threads)} background thread(s) to finish...")
        for tid, t in active_threads.items():
            t.join(timeout=5)  # Wait max 5s per thread
            if t.is_alive():
                print(f"   ⚠️ Thread {tid} still running after timeout, proceeding with shutdown")
    
    # Now safe to close pools
    try:
        _db.pool.close()
    except Exception:
        pass
    try:
        _db._checkpointer_pool.close()
    except Exception:
        pass
    print("✅ All database connection pools closed")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Health Check
# -----------------------------

@app.get("/health")
def health_check():
    """Production health check — verifies DB pool connectivity including SSL."""
    # Check CRUD pool (handles its own reset if closed)
    db_ok = validate_pool()
    
    # Check checkpointer pool (handles its own reset/recovery)
    checkpointer_ok = validate_checkpointer_pool()
    
    import database as _db
    pool_stats = {
        "min_size": _db.pool.min_size,
        "max_size": _db.pool.max_size,
    }
    try:
        pool_stats["size"] = _db.pool.get_stats().get("pool_size", "N/A")
        pool_stats["idle"] = _db.pool.get_stats().get("pool_available", "N/A")
    except Exception:
        pass

    # Overall status considers both pools
    if db_ok and checkpointer_ok:
        status = "healthy"
    elif db_ok or checkpointer_ok:
        status = "degraded"
    else:
        status = "unhealthy"
    
    return {
        "status": status,
        "database": "connected" if db_ok else "disconnected",
        "checkpointer": "connected" if checkpointer_ok else "disconnected",
        "pool": pool_stats,
        "active_sessions": len(active_sessions),
        "background_threads": len(background_threads),
    }


# -----------------------------
# Request Schemas
# -----------------------------

class AgentRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = None  # If not provided, creates new thread
    user_id: Optional[str] = None  # Required when creating a new thread
    deep_research: bool = False  # When True, enables full Tier 3 research workflow
    literature_survey: bool = False  # When True, enables literature survey mode
    persona: str = "default"
    sites: Optional[list[str]] = None  # When provided, restrict web searches to these domains
    parent_checkpoint_id: Optional[str] = None  # For branching from a specific checkpoint
    last_event_id: Optional[str] = None  # For stream reconnection
    # Edit/versioning support
    edit_group_id: Optional[str] = None  # Groups edited messages together (same logical message)
    edit_version: Optional[int] = None  # Version number within the edit group
    original_message_index: Optional[int] = None  # Original position in conversation
    
    @validator('prompt')
    def validate_prompt(cls, v):
        """Validate prompt is not empty and within size limits."""
        if not v or not v.strip():
            raise ValueError('Prompt cannot be empty')
        if len(v) > MAX_PROMPT_LENGTH:
            raise ValueError(f'Prompt exceeds maximum length of {MAX_PROMPT_LENGTH} characters')
        return v.strip()
    
    @validator('sites')
    def validate_sites(cls, v):
        """Validate sites list is within limits."""
        if v and len(v) > MAX_SITES_COUNT:
            raise ValueError(f'Maximum {MAX_SITES_COUNT} site restrictions allowed')
        return v


class CreateThreadRequest(BaseModel):
    title: Optional[str] = None
    user_id: Optional[str] = None  # Supabase auth user ID


class UpdateThreadRequest(BaseModel):
    title: str


class BranchRequest(BaseModel):
    checkpoint_id: str
    title: Optional[str] = None


class EditMessageRequest(BaseModel):
    new_content: str
    checkpoint_id: Optional[str] = None  # Checkpoint to branch from


class SessionStatusRequest(BaseModel):
    thread_id: str

class CreatePersonaRequest(BaseModel):
    user_id: str
    name: str
    instructions: str

class UpdatePersonaRequest(BaseModel):
    name: Optional[str] = None
    instructions: Optional[str] = None

class SetSitesRequest(BaseModel):
    user_id: str
    urls: list[str]

class AddSiteRequest(BaseModel):
    user_id: str
    url: str


class ModelSelectRequest(BaseModel):
    model_key: str


class SyncUserRequest(BaseModel):
    user_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    auth_provider: str = "email"


# -----------------------------
# Pool Recovery Endpoint
# -----------------------------

@app.post("/pools/recover")
def recover_pools():
    """
    Manually trigger recovery of SSL/database connection pools.
    Use this endpoint when experiencing persistent SSL errors.
    """
    results = {"crud_pool": "unknown", "checkpointer_pool": "unknown"}
    
    # Recover CRUD pool
    try:
        reset_pool()
        if validate_pool():
            results["crud_pool"] = "recovered"
        else:
            results["crud_pool"] = "failed"
    except Exception as e:
        results["crud_pool"] = f"error: {str(e)[:100]}"
    
    # Recover checkpointer pool
    try:
        from database import reset_checkpointer_pool, _checkpointer_pool
        reset_checkpointer_pool()
        # Verify recovery
        with _checkpointer_pool.connection(timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        results["checkpointer_pool"] = "recovered"
    except Exception as e:
        results["checkpointer_pool"] = f"error: {str(e)[:100]}"
    
    overall_status = "success" if all(
        v == "recovered" for v in results.values()
    ) else "partial" if any(
        v == "recovered" for v in results.values()
    ) else "failed"
    
    return {
        "status": overall_status,
        "pools": results
    }


# -----------------------------
# User Sync Endpoint
# -----------------------------

@app.post("/users/sync")
def sync_user_endpoint(request: SyncUserRequest):
    """Sync user from Supabase Auth to our users table"""
    result = sync_user(
        user_id=request.user_id,
        email=request.email,
        display_name=request.display_name,
        avatar_url=request.avatar_url,
        auth_provider=request.auth_provider
    )
    
    if result:
        return {
            "success": True,
            "user_id": result["user_id"],
            "email": result["email"],
            "display_name": result["display_name"]
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to sync user")


@app.get("/users/{user_id}")
def get_user_endpoint(user_id: str):
    """Check if a user exists in the database"""
    user = get_user_by_id(user_id)
    if user:
        return {
            "exists": True, 
            "user_id": user["user_id"], 
            "email": user["email"], 
            "display_name": user["display_name"]
        }
    return {"exists": False}


# -----------------------------
# Document Upload & Knowledge Base Endpoints
# -----------------------------

def _inject_upload_context(
    http_request: Request,
    thread_id: str,
    filename: str,
    file_type: str,
    chunk_count: int,
    image_description: str = None,
):
    """
    Inject an upload notification into the LangGraph thread's message history
    so the agent knows about the uploaded file and can use search_knowledge_base.
    """
    from langchain_core.messages import HumanMessage, AIMessage

    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    # Create a user message that tells the agent about the upload
    if file_type == "image" and image_description:
        user_msg = HumanMessage(
            content=(
                f"[SYSTEM: The user uploaded an image '{filename}' to the knowledge base. "
                f"It has been processed and stored ({chunk_count} chunks). "
                f"Image description: {image_description}. "
                f"When the user asks about this image, use the search_knowledge_base tool to retrieve the full description.]"
            )
        )
    else:
        user_msg = HumanMessage(
            content=(
                f"[SYSTEM: The user uploaded a {file_type} '{filename}' to the knowledge base. "
                f"It has been processed and stored ({chunk_count} chunks). "
                f"When the user asks about this file, use the search_knowledge_base tool to retrieve its contents.]"
            )
        )

    # Create an acknowledgment from the agent
    ai_msg = AIMessage(
        content=f"I've received your {file_type} **{filename}** and added it to the knowledge base. You can now ask me questions about it!"
    )

    # Inject both messages into the thread's state
    agent.update_state(config, {"messages": [user_msg, ai_msg]})
    print(f"✅ Injected upload context for '{filename}' into thread {thread_id}")


@app.post("/documents/upload")
def upload_document(
    http_request: Request,
    file: UploadFile = File(...),
    user_id: str = Form(...),
    thread_id: str = Form(None),
):
    """
    Upload a document (PDF or TXT) to the user's knowledge base.
    The file is chunked, embedded, and stored in PGVector for RAG retrieval.
    If thread_id is provided, injects upload context into the agent's conversation history.
    """
    import tempfile
    import os

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    # Validate file type
    content_type = file.content_type or ""
    file_ext = os.path.splitext(file.filename or "")[1].lower()

    is_pdf = content_type == "application/pdf" or file_ext == ".pdf"
    is_text = content_type.startswith("text/") or file_ext in (".txt", ".md", ".csv", ".json")
    is_docx = content_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ) or file_ext in (".doc", ".docx")

    if not (is_pdf or is_text or is_docx):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type or file_ext}. Supported: PDF, TXT, MD, CSV, JSON, DOC, DOCX",
        )

    tmp_path = None
    try:
        # Save uploaded file to a temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            contents = file.file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        # Ingest based on type
        if is_pdf:
            chunk_count = ingest_pdf(
                file_path=tmp_path,
                user_id=user_id,
                metadata={"original_filename": file.filename},
            )
        elif is_docx:
            from docx import Document as DocxDocument
            doc = DocxDocument(tmp_path)
            text_content = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            chunk_count = ingest_text(
                text=text_content,
                user_id=user_id,
                source=file.filename or "uploaded_docx",
                metadata={"original_filename": file.filename},
            )
        else:
            text_content = contents.decode("utf-8", errors="replace")
            chunk_count = ingest_text(
                text=text_content,
                user_id=user_id,
                source=file.filename or "uploaded_text",
                metadata={"original_filename": file.filename},
            )

        # Clean up temp file
        os.unlink(tmp_path)
        tmp_path = None

        # Inject upload context into agent's thread history
        if thread_id:
            try:
                _inject_upload_context(
                    http_request, thread_id, file.filename or "document", "document", chunk_count
                )
            except Exception as inject_err:
                print(f"⚠️ Failed to inject upload context: {inject_err}")

        return {
            "success": True,
            "filename": file.filename,
            "chunks_ingested": chunk_count,
            "message": f"Successfully ingested {chunk_count} chunks from {file.filename}",
        }

    except Exception as e:
        # Clean up temp file on error
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to ingest document: {str(e)}")


@app.post("/documents/upload-image")
def upload_image_document(
    http_request: Request,
    file: UploadFile = File(...),
    user_id: str = Form(...),
    description: str = Form(None),
    thread_id: str = Form(None),
):
    """
    Upload an image to the knowledge base.
    If no description is provided, a multimodal model generates one.
    The description is embedded and stored for retrieval.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    allowed_image_types = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
    if file.content_type not in allowed_image_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: {file.content_type}. Supported: PNG, JPEG, WEBP, GIF",
        )

    try:
        image_bytes = file.file.read()

        # If no description was provided, use Gemini to describe the image
        if not description:
            import base64
            from langchain_google_genai import ChatGoogleGenerativeAI

            vision_model = ChatGoogleGenerativeAI(model="models/gemini-2.5-flash", temperature=0)
            b64_image = base64.b64encode(image_bytes).decode("utf-8")

            response = vision_model.invoke(
                [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Describe this image in detail for a research knowledge base. "
                                    "Include all visible text, data, charts, diagrams, equations, "
                                    "and any other relevant information."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": f"data:{file.content_type};base64,{b64_image}",
                            },
                        ],
                    }
                ]
            )
            description = response.content

        chunk_count = ingest_image_description(
            description=description,
            user_id=user_id,
            image_filename=file.filename or "uploaded_image",
            metadata={"content_type": file.content_type},
        )

        # Inject upload context into agent's thread history
        if thread_id:
            try:
                _inject_upload_context(
                    http_request, thread_id, file.filename or "image", "image", chunk_count,
                    image_description=description[:500] if description else None
                )
            except Exception as inject_err:
                print(f"⚠️ Failed to inject upload context: {inject_err}")

        return {
            "success": True,
            "filename": file.filename,
            "chunks_ingested": chunk_count,
            "description_preview": description[:200] + "..." if len(description) > 200 else description,
            "message": f"Successfully ingested image: {file.filename}",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest image: {str(e)}")


@app.delete("/documents/{user_id}")
def delete_documents(user_id: str):
    """Delete all documents for a specific user from the knowledge base."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    success = delete_user_documents(user_id)
    if success:
        return {"success": True, "message": f"All documents deleted for user {user_id}"}
    raise HTTPException(status_code=500, detail="Failed to delete user documents")


# -----------------------------
# Model Selection Endpoints
# -----------------------------

@app.get("/models")
def get_available_models():
    """Get list of available models grouped by category"""
    # Group models by category
    categories = {}
    for key, config in AVAILABLE_MODELS.items():
        category = config["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append({
            "key": key,
            "name": config["name"],
            "provider": config["provider"],
            "icon": config["icon"]
        })
    
    return {
        "models": categories,
        "current": get_current_model_info()
    }


@app.get("/models/current")
def get_current_model():
    """Get the currently selected model"""
    return get_current_model_info()


@app.post("/models/select")
def select_model(request: ModelSelectRequest, http_request: Request):
    """Select a model to use for future requests (affects main agent only, subagents use fixed model)"""
    if request.model_key not in AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail=f"Unknown model: {request.model_key}")
    
    # Update the current model
    set_current_model(request.model_key)
    
    # REFRESH SUBAGENT MODELS: Update subagents list to use current model logic
    try:
        current_subagent_model = config.subagent_model
        
        # Iterate through the subagents list (imported from main_agent) and update their model
        for subagent_config in subagents:
            if isinstance(subagent_config, dict) and "model" in subagent_config:
                subagent_config["model"] = current_subagent_model
                
        subagent_name = type(current_subagent_model).__name__
        return {
            "status": "success",
            "message": f"Main agent switched to {AVAILABLE_MODELS[request.model_key]['name']}. Subagents switched to {subagent_name}.",
            "current": get_current_model_info()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to switch model: {str(e)}")


# -----------------------------
# Custom Personas Endpoints
# -----------------------------

@app.get("/personas")
def list_personas(user_id: str):
    """Get all custom personas for a user."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        personas = get_custom_personas(user_id)
        return personas
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch personas: {str(e)}")


@app.post("/personas")
def create_persona(request: CreatePersonaRequest):
    """Create a new custom persona."""
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Persona name is required")
    if not request.instructions or not request.instructions.strip():
        raise HTTPException(status_code=400, detail="Persona instructions are required")
    
    result = create_custom_persona(
        user_id=request.user_id,
        name=request.name.strip(),
        instructions=request.instructions.strip()
    )
    if result:
        return result
    raise HTTPException(status_code=500, detail="Failed to create persona")


@app.put("/personas/{persona_id}")
def update_persona(persona_id: str, request: UpdatePersonaRequest, user_id: str = None):
    """Update a custom persona."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id query param is required")
    
    success = update_custom_persona(
        persona_id=persona_id,
        user_id=user_id,
        name=request.name.strip() if request.name else None,
        instructions=request.instructions.strip() if request.instructions else None
    )
    if success:
        return {"status": "updated"}
    raise HTTPException(status_code=404, detail="Persona not found or not owned by user")


@app.delete("/personas/{persona_id}")
def delete_persona(persona_id: str, user_id: str = None):
    """Delete a custom persona."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id query param is required")
    
    success = delete_custom_persona(persona_id=persona_id, user_id=user_id)
    if success:
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Persona not found or not owned by user")


# -----------------------------
# User Sites Endpoints
# -----------------------------

@app.get("/user-sites")
def list_user_sites(user_id: str):
    """Get all saved sites for a user."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    try:
        sites = get_user_sites(user_id)
        return {"sites": sites}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sites: {str(e)}")


@app.put("/user-sites")
def save_user_sites(request: SetSitesRequest):
    """Replace all saved sites for a user."""
    success = set_user_sites(user_id=request.user_id, urls=request.urls)
    if success:
        return {"status": "saved", "count": len(request.urls)}
    raise HTTPException(status_code=500, detail="Failed to save sites")


@app.post("/user-sites")
def add_site(request: AddSiteRequest):
    """Add a single site for a user."""
    if not request.url or not request.url.strip():
        raise HTTPException(status_code=400, detail="URL is required")
    
    success = add_user_site(user_id=request.user_id, url=request.url.strip())
    if success:
        return {"status": "added"}
    return {"status": "already_exists"}  # ON CONFLICT DO NOTHING


@app.delete("/user-sites")
def remove_site(user_id: str, url: str):
    """Remove a single site for a user."""
    if not user_id or not url:
        raise HTTPException(status_code=400, detail="user_id and url are required")
    
    success = remove_user_site(user_id=user_id, url=url)
    if success:
        return {"status": "removed"}
    raise HTTPException(status_code=404, detail="Site not found")


@app.get("/db-status")
def check_database_status():
    """Check database status and ensure default user exists"""
    status = {
        "users_table": False,
        "threads_table": False,
        "store_table": False,
        "default_user_exists": False,
        "thread_count": 0,
        "errors": []
    }
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Check if tables exist and get counts
                try:
                    cur.execute("SELECT COUNT(*) FROM users")
                    user_count = cur.fetchone()[0]
                    status["users_table"] = True
                    status["user_count"] = user_count
                except Exception as e:
                    status["errors"].append(f"users table: {e}")
                
                try:
                    cur.execute("SELECT COUNT(*) FROM threads WHERE status = 'active'")
                    thread_count = cur.fetchone()[0]
                    status["threads_table"] = True
                    status["thread_count"] = thread_count
                except Exception as e:
                    status["errors"].append(f"threads table: {e}")
                
                try:
                    cur.execute("SELECT COUNT(*) FROM store")
                    store_count = cur.fetchone()[0]
                    status["store_table"] = True
                    status["store_count"] = store_count
                except Exception as e:
                    status["errors"].append(f"store table: {e}")
                
                # Check if default user exists
                try:
                    cur.execute(
                        "SELECT user_id FROM users WHERE user_id = %s::uuid",
                        ("00000000-0000-0000-0000-000000000001",)
                    )
                    row = cur.fetchone()
                    status["default_user_exists"] = row is not None
                except Exception as e:
                    status["errors"].append(f"default user check: {e}")
                
        return status
    except Exception as e:
        status["errors"].append(f"connection: {e}")
        return status


@app.post("/db-setup")
def setup_database():
    """Setup default user and ensure tables are ready"""
    results = {"actions": [], "errors": []}
    
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Create default user if not exists
                try:
                    cur.execute(
                        """
                        INSERT INTO users (user_id, email, username, display_name)
                        VALUES ('00000000-0000-0000-0000-000000000001'::uuid, 'default@maira.ai', 'default', 'Default User')
                        ON CONFLICT (user_id) DO NOTHING
                        RETURNING user_id
                        """
                    )
                    row = cur.fetchone()
                    if row:
                        results["actions"].append("Created default user")
                    else:
                        results["actions"].append("Default user already exists")
                except Exception as e:
                    results["errors"].append(f"Failed to create default user: {e}")
                
            conn.commit()
        
        results["status"] = "success" if not results["errors"] else "partial"
        return results
    except Exception as e:
        results["errors"].append(f"Connection failed: {e}")
        results["status"] = "error"
        return results


@app.get("/db-test")
def test_database(request: Request):
    """Test database connection with a simple HI message"""
    try:
        agent = get_agent()
        test_thread_id = f"test-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": test_thread_id}}
        
        # Run a simple "HI" through the agent
        result = agent.invoke(
            {"messages": [("user", "HI")]},
            config=config
        )
        
        return {
            "status": "success",
            "message": "Database connection working! Checkpointer tables are ready.",
            "test_thread_id": test_thread_id,
            "response": result["messages"][-1].content if result.get("messages") else "No response"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database test failed: {str(e)}",
            "error_type": type(e).__name__
        }


# -----------------------------
# Thread Management Endpoints
# -----------------------------

@app.post("/threads", response_model=Dict[str, Any])
def create_thread(request: CreateThreadRequest = None):
    """Create a new conversation thread with UUID v7 - saves to Supabase"""
    title = request.title if request else None
    user_id = request.user_id if request and request.user_id else None
    
    # Require user_id for thread creation
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required to create a thread")
    
    thread = thread_manager.create_thread(title=title)
    
    # Persist to Supabase threads table
    result = create_thread_for_user(thread.thread_id, user_id, thread.title)
    if not result:
        # Check if it failed because user doesn't exist
        if not user_exists(user_id):
            raise HTTPException(status_code=400, detail=f"User {user_id} does not exist. Please sign in again.")
        raise HTTPException(status_code=500, detail="Failed to create thread in database")
    
    return thread.to_dict()


@app.get("/threads", response_model=List[Dict[str, Any]])
def list_threads(user_id: Optional[str] = None):
    """Get all conversation threads from Supabase for a specific user, sorted by newest first"""
    if user_id:
        # Use database function to fetch threads by user
        threads = get_threads_by_user(user_id)
        
        # Sync to in-memory cache for compatibility
        for t in threads:
            if t["thread_id"] not in thread_manager._threads:
                thread_manager._threads[t["thread_id"]] = Thread(
                    thread_id=t["thread_id"],
                    title=t["title"],
                    created_at=t["created_at"],
                    updated_at=t["updated_at"]
                )
        
        return threads
    else:
        # Fallback: return all threads from in-memory (for backward compatibility)
        threads = thread_manager.get_all_threads()
        return [t.to_dict() for t in threads]


@app.get("/threads/{thread_id}", response_model=Dict[str, Any])
def get_thread(thread_id: str, user_id: Optional[str] = None):
    """Get a specific thread by ID from Supabase"""
    thread = get_thread_by_id(thread_id, user_id)
    
    if thread:
        return {
            "thread_id": thread["thread_id"],
            "title": thread["title"],
            "created_at": thread["created_at"],
            "updated_at": thread["updated_at"]
        }
    
    # Fallback to in-memory
    thread = thread_manager.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread.to_dict()


@app.put("/threads/{thread_id}", response_model=Dict[str, Any])
def update_thread(thread_id: str, request: UpdateThreadRequest, user_id: Optional[str] = None):
    """Update thread title in Supabase"""
    # Use database function
    success = db_update_thread_title(thread_id, request.title, user_id)
    
    if success:
        # Sync to in-memory cache
        thread_manager.update_thread_title(thread_id, request.title)
        
        # Fetch updated thread
        thread = get_thread_by_id(thread_id, user_id)
        if thread:
            return {
                "thread_id": thread["thread_id"],
                "title": thread["title"],
                "created_at": thread["created_at"],
                "updated_at": thread["updated_at"]
            }
    
    # Fallback to in-memory
    thread = thread_manager.update_thread_title(thread_id, request.title)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread.to_dict()


@app.delete("/threads/{thread_id}")
def delete_thread_endpoint(thread_id: str, user_id: Optional[str] = None):
    """Delete a thread and all its data from Supabase database"""
    deleted_from_db = False
    
    # Delete from PostgreSQL (Supabase) - SOFT DELETE the thread
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Soft delete the thread (set status and deleted_at)
                # If user_id provided, validate ownership
                if user_id:
                    cur.execute(
                        """
                        UPDATE threads 
                        SET status = 'deleted', deleted_at = NOW() 
                        WHERE thread_id = %s::uuid AND user_id = %s::uuid
                        RETURNING thread_id
                        """,
                        (thread_id, user_id)
                    )
                else:
                    cur.execute(
                        """
                        UPDATE threads 
                        SET status = 'deleted', deleted_at = NOW() 
                        WHERE thread_id = %s::uuid
                        RETURNING thread_id
                        """,
                        (thread_id,)
                    )
                deleted_row = cur.fetchone()
                
                # Also delete from LangGraph's checkpoint tables
                cur.execute(
                    "DELETE FROM checkpoints WHERE thread_id = %s",
                    (thread_id,)
                )
                cur.execute(
                    "DELETE FROM checkpoint_writes WHERE thread_id = %s", 
                    (thread_id,)
                )
                cur.execute(
                    "DELETE FROM checkpoint_blobs WHERE thread_id = %s",
                    (thread_id,)
                )
                
                # Delete from messages table if exists
                try:
                    cur.execute(
                        "DELETE FROM messages WHERE thread_id = %s::uuid",
                        (thread_id,)
                    )
                except Exception:
                    pass  # Table might not exist
                
            conn.commit()
            deleted_from_db = deleted_row is not None
            print(f"✅ Deleted thread {thread_id} from PostgreSQL/Supabase")
    except Exception as e:
        print(f"⚠️ Error deleting thread from PostgreSQL: {e}")
    
    # Delete from in-memory cache
    thread_manager.delete_thread(thread_id)
    
    if not deleted_from_db:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    return {"status": "deleted", "thread_id": thread_id}


@app.get("/threads/{thread_id}/verify-deletion")
def verify_thread_deletion(thread_id: str):
    """Verify that a thread has been completely deleted from Supabase"""
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # Check checkpoints table
                cur.execute(
                    "SELECT COUNT(*) FROM checkpoints WHERE thread_id = %s",
                    (thread_id,)
                )
                checkpoint_count = cur.fetchone()[0]
                
                # Check checkpoint_writes table
                cur.execute(
                    "SELECT COUNT(*) FROM checkpoint_writes WHERE thread_id = %s",
                    (thread_id,)
                )
                writes_count = cur.fetchone()[0]
                
                # Check checkpoint_blobs table
                cur.execute(
                    "SELECT COUNT(*) FROM checkpoint_blobs WHERE thread_id = %s",
                    (thread_id,)
                )
                blobs_count = cur.fetchone()[0]
                
                return {
                    "thread_id": thread_id,
                    "deleted_from_supabase": checkpoint_count == 0 and writes_count == 0 and blobs_count == 0,
                    "checkpoints_remaining": checkpoint_count,
                    "writes_remaining": writes_count,
                    "blobs_remaining": blobs_count,
                    "in_local_cache": thread_manager.thread_exists(thread_id)
                }
    except Exception as e:
        return {
            "thread_id": thread_id,
            "error": str(e),
            "error_type": type(e).__name__
        }


@app.get("/threads/{thread_id}/messages", response_model=Dict[str, Any])
def get_thread_messages(thread_id: str, request: Request):
    """Get all messages for a specific thread"""
    try:
        agent = get_agent()
        # Get state from checkpointer using thread_id config
        config = {"configurable": {"thread_id": thread_id}}
        state = agent.get_state(config)
        
        # If thread exists in checkpointer but not in thread_manager, create it
        if state and state.values and not thread_manager.thread_exists(thread_id):
            thread_manager._threads[thread_id] = Thread(
                thread_id=thread_id,
                title="Recovered Chat"
            )
        
        messages = []
        if state and state.values and "messages" in state.values:
            print(f"📤 GET /threads/{thread_id}/messages - {len(state.values['messages'])} raw messages")
            for idx, msg in enumerate(state.values["messages"]):
                # Debug: Check raw message content for EDIT_META
                raw_content = getattr(msg, 'content', '') if hasattr(msg, 'content') else str(msg)
                has_edit_meta = 'EDIT_META' in (raw_content if isinstance(raw_content, str) else str(raw_content))
                msg_type = getattr(msg, 'type', 'unknown')
                print(f"   [{idx}] type={msg_type} hasEditMeta={has_edit_meta} content={str(raw_content)[:80]}...")
                
                msg_data = _serialize_message(msg)
                if msg_data:
                    messages.append(msg_data)

        # ── Download injection: always look up Supabase for this thread ──────
        # Checkpoint messages have their [DOWNLOAD_PDF] markers stripped during
        # serialization, so msg.download never gets set from the message content.
        # We directly embed the full base64 data so the frontend only needs one
        # round-trip (this endpoint) and does NOT need to call /downloads.
        try:
            supabase_downloads = download_store.get_downloads_from_supabase(thread_id)
            if supabase_downloads:
                print(f"  ☁️  Injecting {len(supabase_downloads)} Supabase download(s) into history messages")
                # Find the last AI/assistant message index
                last_ai_idx = None
                for i in range(len(messages) - 1, -1, -1):
                    m = messages[i]
                    if m.get("type") in ("ai", "assistant") or m.get("role") in ("ai", "assistant", "agent"):
                        last_ai_idx = i
                        break

                if last_ai_idx is not None:
                    # Attach the primary download with full base64 data embedded
                    primary = supabase_downloads[0]
                    messages[last_ai_idx]["download"] = {
                        "filename": primary.get("filename", "report"),
                        "data": primary.get("data", "")  # full base64 — no second /downloads fetch needed
                    }
                    print(f"  📎 Injected full download '{primary.get('filename')}' ({len(primary.get('data',''))} chars) into message [{last_ai_idx}]")
        except Exception as dl_inject_err:
            print(f"  ⚠️ Download injection failed (non-fatal): {dl_inject_err}")

        return {"thread_id": thread_id, "messages": messages}
    except Exception as e:
        return {"thread_id": thread_id, "messages": [], "error": str(e)}




@app.get("/threads/{thread_id}/downloads")
def get_thread_downloads(thread_id: str):
    """Retrieve persisted downloads from Supabase Storage for history reload."""
    try:
        downloads = download_store.get_downloads_from_supabase(thread_id)
        return {"thread_id": thread_id, "downloads": downloads}
    except Exception as e:
        print(f"⚠️ Failed to fetch downloads for {thread_id}: {e}")
        return {"thread_id": thread_id, "downloads": []}

# -----------------------------
# History & Branching Endpoints
# -----------------------------

@app.get("/threads/{thread_id}/history", response_model=Dict[str, Any])
def get_thread_history(thread_id: str, request: Request):
    """Get checkpoint history for time travel functionality"""
    try:
        agent = get_agent()
        config = {"configurable": {"thread_id": thread_id}}
        checkpoints = []
        
        # Use LangGraph's get_state_history for time travel (sync version)
        for state in agent.get_state_history(config):
            checkpoint_info = {
                "checkpoint_id": state.config["configurable"].get("checkpoint_id", ""),
                "thread_id": thread_id,
                "timestamp": datetime.now().isoformat(),  # State doesn't have timestamp, use current
                "message_count": len(state.values.get("messages", [])) if state.values else 0,
                "parent_checkpoint_id": state.parent_config["configurable"].get("checkpoint_id") if state.parent_config else None,
                "metadata": {
                    "is_branch_point": False
                }
            }
            checkpoints.append(checkpoint_info)
        
        return {
            "thread_id": thread_id,
            "checkpoints": checkpoints
        }
    except Exception as e:
        return {"thread_id": thread_id, "checkpoints": [], "error": str(e)}


@app.post("/threads/{thread_id}/branch", response_model=Dict[str, Any])
def branch_from_checkpoint(thread_id: str, request: BranchRequest, http_request: Request):
    """Create a new branch from a specific checkpoint (fork conversation)"""
    try:
        agent = get_agent()
        # Create new thread for the branch
        new_thread = thread_manager.create_branch(
            parent_thread_id=thread_id,
            fork_checkpoint_id=request.checkpoint_id,
            title=request.title
        )
        
        if not new_thread:
            raise HTTPException(status_code=500, detail="Failed to create branch")
        
        # Get the state at the checkpoint
        source_config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": request.checkpoint_id
            }
        }
        
        source_state = agent.get_state(source_config)
        
        if source_state and source_state.values:
            # Copy messages to the new thread
            target_config = {"configurable": {"thread_id": new_thread.thread_id}}
            # Note: The new thread will start fresh and messages will be replayed
            # when the user sends the next message
        
        return {
            **new_thread.to_dict(),
            "fork_checkpoint_id": request.checkpoint_id,
            "parent_thread_id": thread_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/threads/{thread_id}/checkpoints/{checkpoint_id}", response_model=Dict[str, Any])
def get_checkpoint_state(thread_id: str, checkpoint_id: str, request: Request):
    """Get the state at a specific checkpoint for time travel preview"""
    try:
        agent = get_agent()
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id
            }
        }
        
        state = agent.get_state(config)
        
        if not state:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        
        messages = []
        if state.values and "messages" in state.values:
            for msg in state.values["messages"]:
                msg_data = _serialize_message(msg)
                if msg_data:
                    messages.append(msg_data)
        
        return {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "messages": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# Session Status Endpoints
# -----------------------------

@app.get("/sessions/{thread_id}/status")
def get_session_status_endpoint(thread_id: str):
    """Get the status of an active agent session for reconnection support"""
    # Check in-memory first
    if thread_id in active_sessions:
        session = active_sessions[thread_id]
        return {
            "thread_id": thread_id,
            "status": session.get("status", "unknown"),
            "has_active_stream": session.get("status") == "running",
            "event_count": len(session.get("events", [])),
            "last_content": session.get("last_content", ""),
            "prompt": session.get("prompt", ""),
            "deep_research": session.get("deep_research", False)
        }
    
    # Check Redis if not in memory
    if redis_client:
        try:
            key = f"session:{thread_id}"
            session_data = redis_client.hgetall(key)
            if session_data:
                status = session_data.get("status", "unknown")
                deep_research = session_data.get("deep_research", "false")
                # Parse boolean from Redis string
                if isinstance(deep_research, str):
                    deep_research = deep_research.lower() in ("true", "1", "yes")
                
                event_count = 0
                try:
                    event_count = redis_client.llen(f"{key}:events") or 0
                except Exception:
                    pass
                
                return {
                    "thread_id": thread_id,
                    "status": status,
                    "has_active_stream": status == "running",
                    "event_count": event_count,
                    "last_content": session_data.get("last_content", ""),
                    "prompt": session_data.get("prompt", ""),
                    "deep_research": deep_research
                }
        except Exception as e:
            print(f"⚠️ Redis get_session_status failed: {e}")
    
    return {
        "thread_id": thread_id,
        "status": "none",
        "has_active_stream": False,
        "event_count": 0,
        "last_content": "",
        "prompt": "",
        "deep_research": False
    }


@app.get("/sessions/{thread_id}/events")
def get_session_events(thread_id: str, from_index: int = 0):
    """Get buffered events from an active session for reconnection"""
    if thread_id not in active_sessions:
        return {"thread_id": thread_id, "events": [], "status": "none"}
    
    session = active_sessions[thread_id]
    events = session.get("events", [])[from_index:]
    
    return {
        "thread_id": thread_id,
        "events": events,
        "status": session.get("status", "unknown"),
        "total_events": len(session.get("events", []))
    }


@app.post("/sessions/{thread_id}/cancel")
def cancel_session(thread_id: str):
    """
    Cancel an active agent session.
    Sets a threading.Event that the background thread polls every second
    so it can exit even while blocked inside agent.stream() / a tool call.
    """
    if thread_id not in active_sessions:
        return {"thread_id": thread_id, "status": "not_found", "message": "No active session found"}
    
    session = active_sessions[thread_id]
    current_status = session.get("status", "unknown")
    
    if current_status != "running":
        return {
            "thread_id": thread_id, 
            "status": current_status, 
            "message": f"Session is already {current_status}"
        }
    
    # 1. Set the dict-level flag (legacy check still used in a few places)
    session["cancelled"] = True
    session["status"] = "cancelled"
    
    # 2. Signal the threading.Event so the polling loop wakes up immediately
    if thread_id in cancellation_events:
        cancellation_events[thread_id].set()
        print(f"🛑 Cancellation event set for thread {thread_id}")
    
    # 3. Send cancellation event to any connected SSE clients
    if thread_id in message_queues:
        try:
            cancel_event = {
                "type": "cancelled",
                "message": "Generation stopped by user"
            }
            message_queues[thread_id].put_nowait(cancel_event)
        except queue.Full:
            pass
    
    print(f"🛑 Session cancelled for thread {thread_id}")
    
    return {
        "thread_id": thread_id,
        "status": "cancelled",
        "message": "Session cancellation requested"
    }


@app.get("/sessions/{thread_id}/stream")
def reconnect_session_stream(thread_id: str, from_index: int = 0):
    """
    Reconnect to an active session's event stream.
    First replays all buffered events, then streams live updates.
    """
    # Check in-memory first
    session = active_sessions.get(thread_id)
    
    # Check Redis if not in memory
    redis_session = None
    if not session and redis_client:
        try:
            key = f"session:{thread_id}"
            redis_data = redis_client.hgetall(key)
            if redis_data:
                redis_session = redis_data
        except Exception as e:
            print(f"⚠️ Redis reconnect lookup failed: {e}")
    
    if not session and not redis_session:
        raise HTTPException(status_code=404, detail="No active session found")
    
    def get_session_field(field, default=None):
        """Get a field from in-memory session or Redis"""
        if session:
            return session.get(field, default)
        if redis_session:
            val = redis_session.get(field, default)
            # Parse bool/json strings from Redis
            if isinstance(val, str) and val.lower() in ("true", "false"):
                return val.lower() == "true"
            return val
        return default
    
    def reconnect_generator():
        try:
            # 1. First, replay all buffered events from the requested index
            events = []
            if session:
                events = session.get("events", [])
            elif redis_client:
                try:
                    key = f"session:{thread_id}"
                    raw_events = redis_client.lrange(f"{key}:events", from_index, -1)
                    events = [json.loads(e) for e in (raw_events or [])]
                except Exception as e:
                    print(f"⚠️ Redis event replay failed: {e}")

            for i, event in enumerate(events if not session else events[from_index:], start=from_index):
                yield f"data: {json.dumps({**event, 'replayed': True, 'index': i})}\n\n"
            
            last_sent = len(events) if not session else len(events)
            
            # 2. If session is still running, poll the queue for live updates
            status = get_session_field("status", "unknown")
            if status == "running":
                q = message_queues.get(thread_id)
                
                if q:
                    while True:
                        # Re-check status
                        current_status = get_session_field("status", "unknown")
                        if current_status != "running":
                            break
                        try:
                            event = q.get(timeout=30.0)
                            yield f"data: {json.dumps(event)}\n\n"
                            
                            if event.get('type') in ('done', 'error'):
                                break
                        except queue.Empty:
                            # Send keepalive and check status
                            yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                elif session:
                    # No queue, poll the events buffer (in-memory only)
                    while True:
                        current_status = get_session_field("status", "unknown")
                        if current_status != "running":
                            break
                        time.sleep(0.1)
                        current_events = session.get("events", [])
                        if len(current_events) > last_sent:
                            for i, event in enumerate(current_events[last_sent:], start=last_sent):
                                yield f"data: {json.dumps({**event, 'index': i})}\n\n"
                            last_sent = len(current_events)
            
            # 3. Send final status
            final_status = get_session_field("status", "completed")
            yield f"data: {json.dumps({'type': 'reconnect_complete', 'status': final_status})}\n\n"
            
        except Exception as e:
            # Client disconnected during reconnect
            print(f"📡 Client disconnected during reconnect for thread {thread_id}: {e}")
    
    return StreamingResponse(reconnect_generator(), media_type="text/event-stream")


# -----------------------------
# Agent Endpoint
# -----------------------------

# Maximum retries for transient DB/SSL errors during streaming
_MAX_STREAM_RETRIES = 3
_SSL_RETRY_BASE_DELAY = 2  # Base delay in seconds for exponential backoff




def _recover_checkpointer(agent):
    """
    Attempt to recover the checkpointer after an SSL failure.
    Returns the new checkpointer or None if recovery failed.
    """
    try:
        from database import reset_checkpointer_pool, get_checkpointer
        
        # Reset the pool to clear dead SSL connections
        reset_checkpointer_pool()
        
        # FIX 2: Refresh the agent instance so new requests use fresh pools
        get_or_refresh_agent(force_refresh=True)
        
        # Get a fresh checkpointer instance
        new_checkpointer = get_checkpointer()
        
        # Update the CURRENT agent's checkpointer if possible
        # langgraph stores checkpointer in different places depending on version
        if hasattr(agent, 'checkpointer'):
            agent.checkpointer = new_checkpointer
        if hasattr(agent, '_checkpointer'):
            agent._checkpointer = new_checkpointer
        
        # Also try to update via config if available
        if hasattr(agent, 'config') and isinstance(agent.config, dict):
            agent.config['checkpointer'] = new_checkpointer
        
        print("   ✅ Checkpointer recovered successfully")
        return new_checkpointer
    except Exception as e:
        print(f"   ⚠️ Checkpointer recovery failed: {e}")
        return None


def _stream_with_retry(agent, stream_input, config, thread_id, store_event, stop_event: Optional[threading.Event] = None):
    """
    Generator that wraps agent.stream() with automatic retry on transient
    database/SSL errors.  The checkpointer uses its own dedicated pool
    (never reset), so we just wait for its built-in health checks to
    discard bad connections, then retry from the last LangGraph checkpoint.
    """
    attempt = 0
    current_input = stream_input
    last_successful_chunk = None

    while attempt <= _MAX_STREAM_RETRIES:
        # Check if already cancelled before starting
        if stop_event and stop_event.is_set():
            return

        try:
            # 1. Assign the stream to a variable so we can control it
            stream_iter = agent.stream(
                current_input,
                config=config,
                stream_mode="updates"
            )
            try:
                for chunk in stream_iter:
                    # Check for cancellation between chunks
                    if stop_event and stop_event.is_set():
                        print(f"🛑 Cancellation detected in _stream_with_retry for {thread_id}")
                        # NEW: Explicitly assassinate the LangGraph generator
                        stream_iter.close()
                        return

                    last_successful_chunk = chunk
                    yield chunk
                return  # Stream completed successfully
            finally:
                # NEW: Ensure it ALWAYS gets killed if the loop exits
                stream_iter.close()

        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Check if this is a transient error worth retrying
            is_transient = _is_transient_error(error_msg)
            
            # Also check for specific exception types
            is_ssl_error = 'ssl' in error_type.lower() or 'ssl' in error_msg.lower()
            is_connection_error = 'connection' in error_type.lower() or 'connection' in error_msg.lower()
            
            should_retry = (is_transient or is_ssl_error or is_connection_error) and attempt < _MAX_STREAM_RETRIES
            
            if should_retry:
                attempt += 1
                delay = min(_SSL_RETRY_BASE_DELAY * (2 ** (attempt - 1)), 15)  # Exponential backoff, max 15s
                
                print(f"🔄 Stream retry {attempt}/{_MAX_STREAM_RETRIES} for thread {thread_id}")
                print(f"   Error: {error_type}: {error_msg[:100]}...")
                print(f"   Waiting {delay}s before retry...")
                
                # Attempt checkpointer recovery
                _recover_checkpointer(agent)
                
                # Also reset the CRUD pool if needed
                try:
                    ensure_healthy_pool()
                except Exception:
                    pass
                
                time.sleep(delay)

                # Notify frontend about the retry
                store_event({'type': 'content', 'messages': [{
                    'role': 'assistant',
                    'content': f'\n\n> ⚠️ Connection interrupted (attempt {attempt}/{_MAX_STREAM_RETRIES}). Reconnecting...\n\n'
                }]})

                # Resume from last checkpoint — don't re-send user message
                current_input = None
                continue

            raise  # Non-transient or retries exhausted — propagate to caller


# SSL keepalive interval for long-running streams
_SSL_KEEPALIVE_INTERVAL = 30  # Check SSL health every 30 seconds during streaming


def run_agent_background(agent, thread_id: str, prompt: str, config: dict, deep_research: bool, literature_survey: bool = False, persona: str = "default", edit_metadata: Optional[dict] = None, sites: Optional[list[str]] = None, user_id: Optional[str] = None):
    """
    DETACHED BACKGROUND THREAD: Runs the agent independently of HTTP connection.
    This thread continues even if the browser reloads or disconnects.
    
    Args:
        agent: The LangGraph agent instance
        thread_id: Unique thread identifier
        prompt: User's message
        config: Agent configuration
        deep_research: Whether deep research mode is enabled
        literature_survey: Whether literature survey mode is enabled
        persona: The persona to adopt (Student, Professor, Researcher, or custom-{id})
        edit_metadata: Optional dict with edit_group_id, edit_version, original_message_index
        sites: Optional list of domains to restrict search to
        user_id: Optional user ID for fetching custom personas
    """
    import re
    import hashlib
    event_counter = 0
    active_tools = set()  # Track active tools to send completion events
    active_tool_ids = {}  # NEW: Map tool_call_id to display_name
    sent_content_hashes = set()  # Track content already sent to prevent duplicates
    last_ssl_check = time.time()  # Track last SSL health check
    
    # =====================================================
    # ENHANCED STATUS MESSAGES FOR UI DISPLAY
    # These provide clear, user-friendly feedback during deep research
    # =====================================================
    
    # Research phases for deep search mode
    RESEARCH_PHASES = {
        'planning': {'name': 'Planning', 'icon': '📋', 'description': 'Creating research plan'},
        'searching': {'name': 'Searching', 'icon': '🔍', 'description': 'Gathering information'},
        'drafting': {'name': 'Drafting', 'icon': '✍️', 'description': 'Writing content'},
        'reasoning': {'name': 'Reasoning', 'icon': '🧠', 'description': 'Deep reasoning & verification'},
        'finalizing': {'name': 'Finalizing', 'icon': '✨', 'description': 'Completing research'},
    }
    
    # Mapping of tool/agent names to user-friendly status messages with detailed info
    TOOL_STATUS_MESSAGES = {
        # ===== SUBAGENTS (Deep Research Pipeline) =====
        'write_todos': {
            'start': '📋 Updating research plan...',
            'complete': 'Research plan updated',
            'phase': 'planning',
            'detail': 'Managing research steps and progress'
        },
        'websearch-agent': {
            'start': '🌐 Searching the web...',
            'complete': 'Web search complete',
            'phase': 'searching',
            'next_phase': 'drafting',
            'detail': 'Gathering info from web & academic sources'
        },
        'github-agent': {
            'start': '🐙 Analyzing GitHub repository...',
            'complete': 'Repository analysis complete',
            'phase': 'searching',
            'detail': 'Examining code, issues, and documentation'
        },
        'draft-subagent': {
            'start': '✍️ Drafting response...',
            'complete': 'Draft complete',
            'phase': 'drafting',
            'next_phase': 'reasoning',
            'detail': 'Synthesizing findings into a comprehensive answer'
        },
        'deep-reasoning-agent': {
            'start': '🧠 Verifying and reasoning...',
            'complete': 'Verification complete',
            'phase': 'reasoning',
            'next_phase': 'finalizing',
            'detail': 'Cross-checking facts and validating conclusions'
        },
        'summary-agent': {
            'start': '📝 Summarizing findings...',
            'complete': 'Summary complete',
            'phase': 'finalizing',
            'next_phase': 'completed',
            'detail': 'Creating a concise summary of the research'
        },
        'report-subagent': {
            'start': '📄 Generating final report...',
            'complete': 'Report generated',
            'phase': 'finalizing',
            'next_phase': 'completed',
            'detail': 'Compiling all findings into a structured report'
        },
        'literature-survey-agent': {
            'start': '📚 Conducting literature survey...',
            'complete': 'Literature survey complete',
            'phase': 'searching',
            'detail': 'Systematically reviewing academic literature'
        },
        
        # ===== DIRECT TOOLS =====
        'internet_search': {
            'start': '🔍 Searching the internet...',
            'complete': 'Search complete',
            'phase': 'searching',
            'detail': 'Querying search engines for relevant results'
        },
        'arxiv_search': {
            'start': '📖 Searching arXiv...',
            'complete': 'arXiv search complete',
            'phase': 'searching',
            'detail': 'Finding preprints and research papers'
        },
        'search_knowledge_base': {
            'start': '📂 Searching your documents...',
            'complete': 'Document search complete',
            'phase': 'searching',
            'detail': 'Looking through your uploaded files'
        },
        'extract_content': {
            'start': '📄 Extracting content...',
            'complete': 'Content extracted',
            'phase': 'searching',
            'detail': 'Reading and parsing document content'
        },
        
        # ===== EXPORT/CONVERSION TOOLS =====
        'export_to_pdf': {
            'start': '📑 Creating PDF...',
            'complete': 'PDF ready',
            'phase': 'finalizing',
            'detail': 'Converting to PDF format'
        },
        'export_to_docx': {
            'start': '📝 Creating Word document...',
            'complete': 'Document ready',
            'phase': 'finalizing',
            'detail': 'Converting to DOCX format'
        },
        'convert_latex_to_pdf': {
            'start': '📑 Converting LaTeX to PDF...',
            'complete': 'PDF conversion complete',
            'phase': 'finalizing',
            'detail': 'Rendering LaTeX document'
        },
        'convert_latex_to_docx': {
            'start': '📝 Converting to Word...',
            'complete': 'Word document ready',
            'phase': 'finalizing',
            'detail': 'Converting LaTeX to DOCX'
        },
        'convert_latex_to_markdown': {
            'start': '📄 Converting to Markdown...',
            'complete': 'Markdown ready',
            'phase': 'finalizing',
            'detail': 'Converting LaTeX to Markdown'
        },
        'convert_latex_to_all_formats': {
            'start': '📚 Exporting all formats...',
            'complete': 'All formats ready',
            'phase': 'finalizing',
            'detail': 'Creating PDF, DOCX, and Markdown versions'
        },
        'generate_and_convert_document': {
            'start': '📝 Generating document...',
            'complete': 'Document generated',
            'phase': 'drafting',
            'detail': 'Creating formatted document'
        },
        'generate_large_document_with_chunks': {
            'start': '📚 Generating large document...',
            'complete': 'Document generated',
            'phase': 'drafting',
            'detail': 'Creating comprehensive document in sections'
        },
    }
    
    # Progress mapping (0-100) - represents overall research progress
    TOOL_PROGRESS = {
        # Planning phase (0-15%)
        'write_todos': 10,
        
        # Searching phase (15-50%)
        'search_knowledge_base': 20,
        'internet_search': 25,
        'arxiv_search': 30,
        'websearch-agent': 40,
        'github-agent': 45,
        'literature-survey-agent': 50,
        
        # Drafting phase (50-75%)
        'draft-subagent': 65,
        'generate_and_convert_document': 70,
        'generate_large_document_with_chunks': 70,
        
        # Reasoning phase (75-90%)
        'deep-reasoning-agent': 85,
        
        # Finalizing phase (90-100%)
        'summary-agent': 90,
        'report-subagent': 92,
        'export_to_pdf': 95,
        'export_to_docx': 95,
        'convert_latex_to_pdf': 96,
        'convert_latex_to_docx': 96,
        'convert_latex_to_markdown': 96,
        'convert_latex_to_all_formats': 98,
    }
    
    # Track current research phase
    current_phase = 'planning' if deep_research else None
    phase_start_time = time.time()
    last_sent_progress = 0
    
    def store_event(event_data: dict):
        """Store event in session buffer and push to queue"""
        nonlocal event_counter
        event_counter += 1
        event_data['event_id'] = f'{thread_id}_{event_counter}'
        
        append_event(thread_id, event_data)
        
        # Push to queue for any connected clients
        if thread_id in message_queues:
            try:
                message_queues[thread_id].put_nowait(event_data)
            except queue.Full:
                pass  # Queue full, event is still stored in buffer
    
    def get_status_message(tool_name: str, step: str) -> dict:
        """
        Get user-friendly status message and metadata for a tool.
        Returns a dict with message, phase, detail, and icon for rich UI display.
        """
        if tool_name in TOOL_STATUS_MESSAGES:
            tool_info = TOOL_STATUS_MESSAGES[tool_name]
            return {
                'message': tool_info.get(step, f'{tool_name}...'),
                'phase': tool_info.get('phase', 'processing'),
                'detail': tool_info.get('detail', ''),
                'icon': RESEARCH_PHASES.get(tool_info.get('phase', ''), {}).get('icon', '⚙️')
            }
        
        # Default fallback logic for unknown tools/agents
        display_label = tool_name.replace("-", " ").replace("_", " ").title()
        
        # NEW: Smart phase guessing so UI doesn't get stuck!
        guessed_phase = 'searching'
        lower_name = tool_name.lower()
        if any(w in lower_name for w in ['draft', 'write', 'generate', 'document']):
            guessed_phase = 'drafting'
        elif any(w in lower_name for w in ['reason', 'think', 'verify', 'check']):
            guessed_phase = 'reasoning'
        elif any(w in lower_name for w in ['report', 'summary', 'export', 'final', 'pdf', 'docx']):
            guessed_phase = 'finalizing'
            
        return {
            'message': f'Running {display_label}...' if step == 'start' else f'Finished {display_label}',
            'phase': guessed_phase,
            'detail': 'Agent is performing a specialized task',
            'icon': '⚙️'
        }
    
    def send_phase_update(new_phase: str):
        """Send a phase change event to the UI."""
        nonlocal current_phase, phase_start_time
        
        if new_phase != current_phase and new_phase in RESEARCH_PHASES:
            # Prevent regression: don't go back to earlier phases
            # This handles cases where tools like 'write_todos' (planning) are used 
            # during later phases for updates, which shouldn't reset the UI phase.
            phase_keys = list(RESEARCH_PHASES.keys())
            try:
                current_idx = phase_keys.index(current_phase) if current_phase in phase_keys else -1
                new_idx = phase_keys.index(new_phase)
                
                if new_idx < current_idx:
                    # logger.debug(f"  Start of phase '{new_phase}' ignored because we are already in '{current_phase}'")
                    return
            except ValueError:
                pass

            # Calculate time spent in previous phase
            phase_duration = time.time() - phase_start_time
            
            current_phase = new_phase
            phase_start_time = time.time()
            phase_info = RESEARCH_PHASES[new_phase]
            
            phase_event = {
                'type': 'phase',
                'phase': new_phase,
                'name': phase_info['name'],
                'icon': phase_info['icon'],
                'description': phase_info['description']
            }
            store_event(phase_event)
            logger.info(f"  🏁 Phase: {phase_info['icon']} {phase_info['name']}")
            narrator.on_phase(new_phase)
    
    def extract_thinking(content: str) -> tuple:
        """
        Extract thinking/reasoning blocks from content.
        Returns (thinking_content, cleaned_content)
        """
        thinking_content = None
        cleaned_content = content
        
        # Handle <think> tags
        think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
        if think_match:
            thinking_content = think_match.group(1).strip()
            cleaned_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        
        # Handle <thinking> tags (alternative format)
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', content, re.DOTALL)
        if thinking_match:
            thinking_content = thinking_match.group(1).strip()
            cleaned_content = re.sub(r'<thinking>.*?</thinking>', '', cleaned_content, flags=re.DOTALL).strip()
        
        # Handle Claude-style reasoning (lines starting with "Thinking:" or "Reasoning:")
        reasoning_match = re.search(r'^(Thinking:|Reasoning:)\s*(.+?)(?=\n\n|$)', content, re.MULTILINE | re.DOTALL)
        if reasoning_match and not thinking_content:
            thinking_content = reasoning_match.group(2).strip()
            cleaned_content = re.sub(r'^(Thinking:|Reasoning:)\s*.+?(?=\n\n|$)', '', cleaned_content, flags=re.MULTILINE | re.DOTALL).strip()
        
        return thinking_content, cleaned_content

    # ─── Synthetic Thinking Narrator ──────────────────────────────────────────
    # Gemini doesn't emit <think> tags, so we synthesise a rich, contextual
    # reasoning trace from agent actions and emit it as 'thinking' SSE events.
    # This powers the ReasoningBlock for ALL queries, not just deep-research.
    # ──────────────────────────────────────────────────────────────────────────

    class ThinkingNarrator:
        TOOL_NARRATIVES = {
            # Web / Search
            'internet_search':        ("🔍 Searching the web",              "Querying search engines for relevant, up-to-date information on this topic."),
            'web_search':             ("🌐 Web search",                     "Retrieving and scanning recent web results to gather factual context."),
            'extract_content':        ("📄 Reading page content",           "Extracting and parsing the full text from relevant web pages."),
            # Arxiv / Academic
            'arxiv_search':           ("📚 Searching arXiv",                "Querying the arXiv preprint database for peer-reviewed academic papers."),
            'academic-paper-agent':   ("🎓 Academic literature scan",       "Searching and summarising relevant academic papers and research findings."),
            'paper_reader':           ("📖 Reading paper",                  "Parsing the full text of academic papers to extract key findings and methods."),
            # Reasoning / Drafting
            'deep-reasoning-agent':   ("🧠 Deep reasoning pass",            "Performing a thorough cross-verification and logical analysis of the gathered evidence."),
            'draft-subagent':         ("✍️  Drafting response",              "Structuring and composing a well-organised, evidence-backed answer."),
            'websearch-agent':        ("🔎 Comprehensive web research",     "Running parallel searches across multiple sources to build a complete picture."),
            # Reports / Export
            'report-subagent':        ("📝 Generating report",              "Compiling all findings into a structured, formatted research document."),
            'summary-agent':          ("📋 Summarising findings",           "Distilling the most important insights from the collected research."),
            'export_to_pdf':          ("📄 Exporting to PDF",               "Converting the completed report into a downloadable PDF file."),
            'export_to_docx':         ("📝 Exporting to DOCX",              "Converting the completed report into a downloadable Word document."),
            # Verification
            'validate_citations':     ("✅ Validating citations",           "Cross-checking all cited sources for accuracy and accessibility."),
            'fact_check_claims':      ("🔬 Fact-checking claims",           "Verifying factual statements against authoritative sources."),
            'assess_content_quality': ("📊 Assessing quality",              "Evaluating response completeness, coherence, and factual integrity."),
            # GitHub / Code
            'github-agent':           ("💻 Searching GitHub",               "Looking through code repositories and technical documentation on GitHub."),
        }
        PHASE_NARRATIVES = {
            'planning':   "Step 1: Planning — analysing the query and deciding which research strategies to employ.",
            'searching':  "Step 2: Searching — dispatching queries across web, academic, and specialised sources.",
            'analyzing':  "Step 3: Analysing — reading, cross-referencing, and synthesising the retrieved material.",
            'drafting':   "Step 4: Drafting — composing a structured, evidence-backed response.",
            'reasoning':  "Step 5: Reasoning — verifying facts, checking citations, and stress-testing the draft.",
            'finalizing': "Step 6: Finalising — polishing the response and preparing any downloadable outputs.",
        }

        def __init__(self):
            self.step = 0
            self.seen_tools: set = set()
            self.last_tool_narrated: str = ""

        def _emit(self, text: str, phase: str = ""):
            self.step += 1
            event = {'type': 'thinking', 'content': f"Step {self.step}: {text}\n", 'phase': phase or current_phase}
            store_event(event)

        def on_query_start(self, user_prompt: str, mode: str):
            short = user_prompt[:120].replace('\n', ' ')
            self._emit(f'Received query: "{short}"')
            if mode == 'deep_research':
                self._emit("Mode: Deep Research — will run multi-phase web + academic research pipeline.")
            elif mode == 'literature_survey':
                self._emit("Mode: Literature Survey — will search arXiv and academic sources exhaustively.")
            else:
                self._emit("Mode: Chat — will answer directly with supporting web research where needed.")

        def on_phase(self, phase: str):
            narrative = self.PHASE_NARRATIVES.get(phase)
            if narrative:
                self._emit(narrative, phase)

        def on_tool_start(self, tool_name: str, tool_args: dict):
            if tool_name in self.seen_tools:
                return
            self.seen_tools.add(tool_name)
            label, detail = self.TOOL_NARRATIVES.get(
                tool_name, (f"⚙️  Running {tool_name}", f"Invoking the {tool_name} tool to gather information.")
            )
            args_hint = ""
            if isinstance(tool_args, dict):
                q = tool_args.get('query') or tool_args.get('name') or tool_args.get('prompt') or tool_args.get('topic')
                if q:
                    args_hint = f' — query: "{str(q)[:80]}"'
            self._emit(f"{label}{args_hint}. {detail}")

        def on_tool_done(self, tool_name: str, result_chars: int):
            label, _ = self.TOOL_NARRATIVES.get(tool_name, (tool_name, ""))
            if result_chars > 0:
                self._emit(f"{label} complete — retrieved {result_chars:,} characters of data.")

        def on_content_start(self):
            self._emit("Synthesising answer — weaving together all gathered evidence into a coherent response.")

        def on_done(self):
            self._emit("Response complete. All sources corroborated and answer finalised.")

    narrator = ThinkingNarrator()
    
    try:
        # Determine research mode for UI display
        if literature_survey:
            mode = 'literature_survey'
            mode_display = 'Literature Survey'
            mode_prefix = "[MODE: LITERATURE_SURVEY] "
        elif deep_research:
            mode = 'deep_research'
            mode_display = 'Deep Research'
            mode_prefix = "[MODE: DEEP_RESEARCH] "
        else:
            mode = 'chat'
            mode_display = 'Chat'
            mode_prefix = "[MODE: CHAT] "
        
        # Send enhanced init event with mode info for UI
        init_event = {
            'thread_id': thread_id,
            'type': 'init',
            'mode': mode,
            'mode_display': mode_display,
            'deep_research': deep_research,
            'literature_survey': literature_survey,
            'phases': list(RESEARCH_PHASES.keys()) if deep_research else None
        }
        store_event(init_event)

        # Kick off the narrator — emits initial thinking steps immediately
        narrator.on_query_start(prompt, mode)

        # Send initial phase if in deep research mode
        if deep_research:
            send_phase_update('planning')
            narrator.on_phase('planning')
        
        # Buffer to hold download events - sent AFTER all content to keep summary + download in sync
        buffered_download_event = None
        download_marker_seen = False
        
        # Add persona instruction - ALWAYS include it for agent awareness
        persona_instruction = ""
        persona_value = persona.lower() if persona else "default"
        
        print(f"🚀 Background thread started for thread {thread_id}")
        print(f"   📋 Persona received: '{persona}' (type: {type(persona).__name__})")
        print(f"   🔍 Deep Research: {deep_research}")
        print(f"   📚 Literature Survey: {literature_survey}")
        
        if deep_research and not literature_survey:
            if persona_value == "student":
                persona_instruction = "\n[PERSONA: STUDENT - Explain concepts simply, use analogies, be encouraging, avoid jargon]"
            elif persona_value == "professor":
                persona_instruction = "\n[PERSONA: PROFESSOR - Be academic, authoritative, cite sources, encourage critical thinking]"
            elif persona_value == "researcher":
                persona_instruction = "\n[PERSONA: RESEARCHER - Be technical, data-driven, focus on methodology and results]"
            elif persona_value.startswith("custom-") and user_id:
                # Fetch custom persona from DB
                try:
                    persona_id = persona_value.replace("custom-", "")
                    custom_personas = get_custom_personas(user_id)
                    found_persona = next((p for p in custom_personas if p["persona_id"] == persona_id), None)
                    if found_persona:
                        # Clean instructions to remove newlines for compact log
                        safe_instr = found_persona['instructions'].replace('\n', ' ')
                        persona_instruction = f"\n[PERSONA: {found_persona['name']} - {safe_instr}]"
                        print(f"   👤 Applied custom persona: {found_persona['name']}")
                except Exception as e:
                    print(f"   ⚠️ Failed to load custom persona {persona_value}: {e}")
                    persona_instruction = "\n[PERSONA: DEFAULT - Professional, balanced research assistant style]"
            else:
                # Even for "default", add a tag so agents are aware
                persona_instruction = "\n[PERSONA: DEFAULT - Professional, balanced research assistant style]"
        
        # Initialize user content
        user_content = f"{mode_prefix}{prompt}{persona_instruction}"
        
        # Add site restrictions if provided
        if sites and len(sites) > 0:
            site_list = ", ".join(sites)
            user_content += f"\n[CONSTRAINT: RESTRICT SEARCH TO DOMAINS: {site_list}. When using web search tools, always include 'site:domain' operators to restrict results to these sites.]"
            print(f"   🌐 Applied site restrictions: {site_list}")
        
        print(f"   💬 Final message preview: {user_content[:150]}...")
        
        # Pre-validate database connection before starting the long stream
        try:
            ensure_healthy_pool()
        except Exception as pool_err:
            print(f"⚠️ Pool pre-validation failed: {pool_err}")
        
        # Build message input with edit metadata EMBEDDED in content (survives serialization)
        # Format: [EDIT_META:{"g":"groupId","v":1,"i":0}] at the start of content
        from langchain_core.messages import HumanMessage
        import json as _json
        
        final_content = user_content
        if edit_metadata:
            # Embed edit metadata in content - this survives LangGraph checkpoint serialization
            edit_meta_str = _json.dumps({
                "g": edit_metadata.get("edit_group_id"),
                "v": edit_metadata.get("edit_version"),
                "i": edit_metadata.get("original_message_index")
            })
            final_content = f"[EDIT_META:{edit_meta_str}]{user_content}"
            print(f"   ✏️ Edit mode: group={edit_metadata.get('edit_group_id')}, version={edit_metadata.get('edit_version')}")
            print(f"   ✏️ Final content starts with: {final_content[:100]}...")
        
        message_input = HumanMessage(content=final_content)
        print(f"   📝 HumanMessage content preview: {message_input.content[:120] if isinstance(message_input.content, str) else str(message_input.content)[:120]}...")
        
        # ─── CANCELLATION-AWARE STREAMING ─────────────────────────────────────
        # Run the LangGraph stream in a SEPARATE daemon thread so that the outer
        # background thread can poll for cancellation every second instead of
        # blocking indefinitely inside agent.stream() / a tool call.
        #
        # Architecture:
        #   stream_thread  ──chunks──►  chunk_queue  ──►  outer loop (polls + checks cancel)
        #
        # Sentinel object placed in the queue when the stream_thread finishes.
        # ──────────────────────────────────────────────────────────────────────
        _STREAM_DONE = object()  # Unique sentinel
        chunk_queue: queue.Queue = queue.Queue(maxsize=500)
        stream_exception: list = []  # Mutable container so the inner thread can write

        # Create / reset the per-thread cancellation Event
        cancel_evt = threading.Event()
        cancellation_events[thread_id] = cancel_evt

        # 1. Assign the stream to a variable so we can control it
        langgraph_stream = _stream_with_retry(
            agent,
            {"messages": [message_input]},
            config, thread_id, store_event,
            stop_event=cancel_evt
        )

        def _stream_worker():
            """Inner daemon thread: runs agent.stream() and puts chunks into chunk_queue."""
            try:
                for _chunk in langgraph_stream:
                    chunk_queue.put(_chunk)
            except (Exception, GeneratorExit) as _exc:
                # GeneratorExit is handled by finally
                if not isinstance(_exc, GeneratorExit):
                    stream_exception.append(_exc)
            finally:
                langgraph_stream.close()
                chunk_queue.put(_STREAM_DONE)

        stream_thread = threading.Thread(target=_stream_worker, daemon=True)
        stream_thread.start()

        # Outer loop: read chunks from the queue with a 1-second timeout
        # so we can check for cancellation between reads.
        _cancelled = False
        while True:
            # Re-check whether cancel was already requested (dict flag, for compat)
            if active_sessions.get(thread_id, {}).get("cancelled") or cancel_evt.is_set():
                print(f"🛑 Cancellation detected for thread {thread_id}, abandoning stream...")
                # NEW: Explicitly assassinate the LangGraph generator
                langgraph_stream.close()
                cancelled_event = {'type': 'cancelled', 'message': 'Generation stopped by user'}
                store_event(cancelled_event)
                _cancelled = True
                break

            try:
                chunk = chunk_queue.get(timeout=1.0)
            except queue.Empty:
                # No chunk yet — check cancellation and loop
                continue

            if chunk is _STREAM_DONE:
                # Stream finished normally (or with exception)
                break

            # ── re-inject the cancellation check that was previously inside the loop ──
            if active_sessions.get(thread_id, {}).get("cancelled") or cancel_evt.is_set():
                print(f"🛑 Cancellation detected for thread {thread_id}, abandoning stream...")
                # NEW: Explicitly assassinate the LangGraph generator
                langgraph_stream.close()
                cancelled_event = {'type': 'cancelled', 'message': 'Generation stopped by user'}
                store_event(cancelled_event)
                _cancelled = True
                break
            
            # CHECK FOR SERVER SHUTDOWN (uvicorn --reload)
            if _shutting_down:
                print(f"ℹ️ Server shutting down, stopping thread {thread_id}")
                # NEW: Explicitly assassinate the LangGraph generator
                langgraph_stream.close()
                break
            
            # Process each node's output in the chunk
            for node_name, node_output in chunk.items():
                # Handle Overwrite objects at the node level
                if hasattr(node_output, '__class__') and node_output.__class__.__name__ == 'Overwrite':
                    if hasattr(node_output, 'value'):
                        node_output = node_output.value
                    else:
                        continue
                
                if isinstance(node_output, dict) and "messages" in node_output:
                    messages_data = node_output["messages"]
                    
                    # Handle Overwrite for messages field
                    if hasattr(messages_data, '__class__') and messages_data.__class__.__name__ == 'Overwrite':
                        if hasattr(messages_data, 'value'):
                            messages_data = messages_data.value
                        else:
                            continue
                    
                    # Ensure messages_data is iterable
                    if not hasattr(messages_data, '__iter__') or isinstance(messages_data, (str, bytes)):
                        continue
                    
                    for msg in messages_data:
                        # 1. Detect TOOL/SUBAGENT START - when agent decides to use a tool
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                tool_name = tool_call.get("name", "") if isinstance(tool_call, dict) else getattr(tool_call, "name", "")
                                tool_args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
                                tool_id = tool_call.get("id", "") if isinstance(tool_call, dict) else getattr(tool_call, "id", "") # NEW
                                
                                # Extract the true subagent name from generic tool wrappers
                                if tool_name in ["task", "subagent", "delegate", "call_subagent"]:
                                    # Fix: LangChain sometimes passes args as a raw JSON string
                                    if isinstance(tool_args, str):
                                        try:
                                            import json as _json
                                            tool_args = _json.loads(tool_args)
                                        except:
                                            pass
                                            
                                    if isinstance(tool_args, dict):
                                        # Aggressively look for the real name across all possible keys
                                        display_name = tool_args.get("subagent") or \
                                                       tool_args.get("agent") or \
                                                       tool_args.get("name") or \
                                                       tool_args.get("agent_name") or \
                                                       tool_args.get("tool") or \
                                                       tool_args.get("action")
                                        
                                        # Ultimate fallback: check if any value matches a known tool
                                        if not display_name:
                                            for val in tool_args.values():
                                                if isinstance(val, str) and val in TOOL_STATUS_MESSAGES:
                                                    display_name = val
                                                    break
                                                    
                                        display_name = display_name or "subagent"
                                    else:
                                        display_name = "subagent"
                                else:
                                    display_name = tool_name
                                
                                # NEW: Save the ID mapping
                                if tool_id:
                                    active_tool_ids[tool_id] = display_name
                                
                                if display_name and display_name not in active_tools:
                                    active_tools.add(display_name)
                                    progress_val = TOOL_PROGRESS.get(display_name)
                                    # LATCH: Progress only moves forward
                                    if progress_val is not None:
                                        last_sent_progress = max(last_sent_progress, progress_val)
                                    
                                    status_info = get_status_message(display_name, 'start')
                                    tool_phase = status_info.get('phase')
                                    
                                    # Update phase if needed (deep research mode)
                                    if deep_research and tool_phase:
                                        send_phase_update(tool_phase)
                                    
                                    # Use effective phase for UI to avoid visual regression
                                    ui_phase = tool_phase or 'processing'
                                    if deep_research and tool_phase and current_phase:
                                        # Only override if tool_phase is effectively an earlier phase than current_phase
                                        phase_keys = list(RESEARCH_PHASES.keys())
                                        try:
                                            if tool_phase in phase_keys and current_phase in phase_keys:
                                                if phase_keys.index(tool_phase) < phase_keys.index(current_phase):
                                                    ui_phase = current_phase
                                        except ValueError:
                                            pass

                                    status_event = {
                                        "type": "status",
                                        "step": "start",
                                        "agent": node_name,
                                        "tool": display_name,
                                        "message": status_info['message'],
                                        "detail": status_info.get('detail', ''),
                                        "phase": ui_phase,
                                        "icon": status_info.get('icon', '⚙️'),
                                        "progress": last_sent_progress
                                    }
                                    store_event(status_event)
                                    logger.info(f"  🔧 [{node_name}] {status_info['message']}")
                                    # Emit narrator step for this tool
                                    narrator.on_tool_start(display_name, tool_args)
                        
                        # 2. Detect TOOL COMPLETION - when tool returns result
                        msg_type = getattr(msg, "type", None) or (msg.get("type") if isinstance(msg, dict) else None)
                        msg_name = getattr(msg, "name", None) or (msg.get("name") if isinstance(msg, dict) else None)
                        
                        # NEW: Recover the real subagent name using the tool_call_id
                        tool_id = getattr(msg, "tool_call_id", None) or (msg.get("tool_call_id") if isinstance(msg, dict) else None)
                        if tool_id and tool_id in active_tool_ids:
                            msg_name = active_tool_ids.pop(tool_id)

                        msg_content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
                        
                        # 2a. CRITICAL: Intercept download markers from ANY message type BEFORE they can be corrupted
                        # This ensures base64 data is sent directly to frontend without LLM modification
                        # Check both tool outputs AND AI messages (for when subagent returns pass through main agent)
                        
                        # Normalize content to string (Gemini returns array format)
                        content_to_check = msg_content
                        if isinstance(msg_content, list):
                            content_to_check = ''.join(
                                item.get('text', '') if isinstance(item, dict) else str(item) 
                                for item in msg_content
                            )
                        
                        if isinstance(content_to_check, str) and content_to_check:
                            for marker in ["[DOWNLOAD_PDF]", "[DOWNLOAD_DOCX]", "[DOWNLOAD_MD]"]:
                                if marker in content_to_check:
                                    print(f"  🔍 Found {marker} in message (type: {msg_type}, content length: {len(content_to_check)})")
                                    try:
                                        marker_idx = content_to_check.index(marker)
                                        after_marker = content_to_check[marker_idx + len(marker):]
                                        
                                        # Use .find() instead of .index() to avoid ValueError
                                        brace_pos = after_marker.find("{")
                                        if brace_pos == -1:
                                            print(f"  ⚠️ Marker found but no JSON payload (no opening brace), skipping")
                                            continue
                                        
                                        json_start = marker_idx + len(marker) + brace_pos
                                        
                                        # Find matching closing brace using brace counting
                                        brace_count = 0
                                        json_end = json_start
                                        found_end = False
                                        for i, char in enumerate(content_to_check[json_start:], json_start):
                                            if char == '{':
                                                brace_count += 1
                                            elif char == '}':
                                                brace_count -= 1
                                                if brace_count == 0:
                                                    json_end = i
                                                    found_end = True
                                                    break
                                        
                                        if not found_end:
                                            print(f"  ⚠️ Incomplete JSON payload (no matching closing brace), skipping")
                                            continue
                                        
                                        json_str = content_to_check[json_start:json_end + 1]
                                        download_data = json.loads(json_str, strict=False)
                                        
                                        # Check if the JSON contains actual base64 data
                                        # (latex tools now return short status JSON without data;
                                        #  full data is stored via _store_pending_download)
                                        if download_data.get("data"):
                                            # Full inline data — buffer it directly
                                            buffered_download_event = {
                                                "type": "download",
                                                "filename": download_data.get("filename", "download"),
                                                "data": download_data["data"]
                                            }
                                            print(f"  📥 Download buffered from {msg_type}: {download_data.get('filename')} ({len(download_data['data'])} bytes)")
                                        else:
                                            # Short status JSON (no data) — will use fallback path
                                            print(f"  📋 Download marker detected (status only): {download_data.get('filename')} — will recover from tool storage")
                                            # Mark that we saw the marker so we know to look for it
                                            download_marker_seen = True
                                    except (json.JSONDecodeError, ValueError, IndexError) as e:
                                        print(f"  ⚠️ Failed to parse download marker: {e}")
                        
                        if msg_type == "tool":
                            # Use msg_name (which was updated by tool_id logic above)
                            if msg_name and msg_name in active_tools:
                                active_tools.discard(msg_name)
                                status_info = get_status_message(msg_name, 'complete')
                                status_event = {
                                    "type": "status",
                                    "step": "complete",
                                    "tool": msg_name,
                                    "message": status_info['message'],
                                    "phase": status_info.get('phase', 'processing'),
                                    "icon": '✅',
                                    "progress": last_sent_progress
                                }
                                store_event(status_event)
                                
                                # Advance phase if this was a phase-terminating subagent
                                next_phase = TOOL_STATUS_MESSAGES.get(msg_name, {}).get('next_phase')
                                if deep_research and next_phase:
                                    send_phase_update(next_phase)
                                logger.info(f"  ✅ {status_info['message']}")
                                # Narrator: tool finished — report how much data it produced
                                result_len = len(str(msg_content)) if msg_content else 0
                                narrator.on_tool_done(msg_name, result_len)
                            elif msg_name == "task":
                                logger.warning(f"  ⚠️ Generic 'task' completion detected without successful ID mapping.")
            
                # Also serialize and send the regular update
            serialized = _serialize_chunk(chunk)
            if serialized:
                # Defensive sanitization: strip any inline download markers and payloads
                # from serialized messages. Inline base64 can be truncated by the LLM
                # and should never be propagated to the frontend; tool-storage events
                # are emitted later and contain the full data.
                try:
                    if isinstance(serialized.get('messages'), list):
                        for m in serialized['messages']:
                            c = m.get('content') if isinstance(m, dict) else None
                            if isinstance(c, str) and ("[DOWNLOAD_PDF]" in c or "[DOWNLOAD_DOCX]" in c or "[DOWNLOAD_MD]" in c):
                                # Remove the marker and any following JSON/base64 payload
                                import re as _re
                                cleaned = _re.sub(r'\[DOWNLOAD_[A-Z]+\].*$', '', c, flags=_re.DOTALL).strip()
                                m['content'] = cleaned or 'Report generated successfully! Click below to download.'
                                print(f"  🔒 Stripped inline download marker from serialized message (len before: {len(c)})")
                except Exception as _san_e:
                    print(f"  ⚠️ Failed to sanitize serialized message: {_san_e}")

            if serialized:
                # Deduplicate: skip messages with content we've already sent
                if serialized.get('messages'):
                    deduped_messages = []
                    for msg in serialized['messages']:
                        content = msg.get('content', '')
                        if isinstance(content, str) and content.strip():
                            # Create hash of first 200 chars to detect duplicates
                            # (full content may differ slightly due to streaming)
                            content_key = hashlib.md5(content.strip()[:200].encode()).hexdigest()
                            if content_key in sent_content_hashes:
                                print(f"  ⏭️ Skipping duplicate content (hash: {content_key[:8]}...)")
                                continue
                            sent_content_hashes.add(content_key)
                        deduped_messages.append(msg)
                    
                    if not deduped_messages:
                        continue  # All messages were duplicates, skip this update
                    serialized['messages'] = deduped_messages
                
                # Check for reasoning/thinking blocks in content and extract them
                if serialized.get('messages'):
                    msgs = serialized['messages']
                    msg_list_to_check = [msgs[-1]] if msgs else []
                    
                    for msg in msg_list_to_check:
                        content = msg.get('content', '')
                        if isinstance(content, str):
                            # Use enhanced thinking extraction
                            thinking_content, cleaned_content = extract_thinking(content)
                            
                            if thinking_content:
                                # Send thinking/reasoning as separate event for UI display
                                reasoning_event = {
                                    'type': 'thinking',
                                    'content': thinking_content,
                                    'phase': current_phase
                                }
                                store_event(reasoning_event)
                                logger.debug(f"  💭 Thinking extracted ({len(thinking_content)} chars)")
                            
                            # Update message with cleaned content
                            if cleaned_content != content:
                                msg['content'] = cleaned_content
                
                store_event(serialized)
        
        # Re-raise any exception that occurred inside the stream_worker thread
        if stream_exception:
            raise stream_exception[0]
        
        # If the session was cancelled, skip the download/done sending path
        if _cancelled:
            update_session_status(thread_id, "cancelled")
            logger.info(f"🛑 Thread {thread_id} was cancelled by user.")

        else:
            # Send buffered download event AFTER all content has been streamed
            # This ensures the summary text arrives before the download button
            # Collect ALL pending downloads (PDF, DOCX, LaTeX) - don't short-circuit!
            from tools.pdftool import get_pending_download as get_pdf_download
            from tools.doctool import get_pending_download as get_docx_download
            from tools.latextoformate import get_pending_download as get_latex_download
            
            all_downloads = []
            if buffered_download_event:
                all_downloads.append(buffered_download_event)
            
            # Check each tool's storage independently (no short-circuit)
            pdf_pending = get_pdf_download()
            if pdf_pending and pdf_pending.get("data"):
                all_downloads.append({
                    "type": "download",
                    "filename": pdf_pending.get("filename", "download.pdf"),
                    "data": pdf_pending.get("data", "")
                })
                print(f"  📥 PDF recovered from tool storage: {pdf_pending.get('filename')} ({len(pdf_pending.get('data', ''))} bytes)")
            
            docx_pending = get_docx_download()
            if docx_pending and docx_pending.get("data"):
                all_downloads.append({
                    "type": "download",
                    "filename": docx_pending.get("filename", "download.docx"),
                    "data": docx_pending.get("data", "")
                })
                print(f"  📥 DOCX recovered from tool storage: {docx_pending.get('filename')} ({len(docx_pending.get('data', ''))} bytes)")
            
            latex_pending = get_latex_download()
            if latex_pending and latex_pending.get("data"):
                all_downloads.append({
                    "type": "download",
                    "filename": latex_pending.get("filename", "download"),
                    "data": latex_pending.get("data", "")
                })
                print(f"  📥 LaTeX recovered from tool storage: {latex_pending.get('filename')} ({len(latex_pending.get('data', ''))} bytes)")
            
            if not all_downloads and download_marker_seen:
                print(f"  ⚠️ Download marker was seen in stream but no data found in tool storage")
                # Fallback: try Supabase in case tools uploaded there before SSL crash
                try:
                    supabase_downloads = download_store.get_downloads_from_supabase(thread_id)
                    for sd in supabase_downloads:
                        all_downloads.append({
                            "type": "download",
                            "filename": sd.get("filename", "download"),
                            "data": sd.get("data", "")
                        })
                    if supabase_downloads:
                        print(f"  ☁️  Recovered {len(supabase_downloads)} download(s) from Supabase fallback")
                except Exception as sb_err:
                    print(f"  ⚠️ Supabase fallback failed: {sb_err}")
            
            # Send all download events AND persist to Supabase for history reload
            for download_event in all_downloads:
                time.sleep(0.3)  # Small delay between downloads
                store_event(download_event)
                print(f"  📥 Download event sent: {download_event.get('filename')}")
                # Persist to Supabase so reloads from history can retrieve the file
                try:
                    download_store.save_to_supabase(
                        thread_id,
                        download_event.get("filename", "download"),
                        download_event.get("data", "")
                    )
                except Exception as save_err:
                    print(f"  ⚠️ Supabase persist failed (non-fatal): {save_err}")
            
            # Send final phase update if in deep research mode
            if deep_research:
                send_phase_update('finalizing')
            
            # Calculate total processing time
            total_time = time.time() - phase_start_time if phase_start_time else 0
            
            # Send completion event with final checkpoint ID and stats
            final_state = agent.get_state(config)
            checkpoint_id = final_state.config["configurable"].get("checkpoint_id", "") if final_state else ""
            # Narrator: wrap up the thinking trace before sending done
            narrator.on_content_start()
            narrator.on_done()

            done_event = {
                'type': 'done',
                'checkpoint_id': checkpoint_id,
                'mode': mode if 'mode' in dir() else 'chat',
                'duration_seconds': round(total_time, 2),
                'downloads_count': len(all_downloads) if 'all_downloads' in dir() else 0
            }
            store_event(done_event)
            
            # Mark session as completed
            update_session_status(thread_id, "completed", {"completed_at": datetime.now().isoformat()})
            
            logger.info(f"✅ Completed thread {thread_id} in {total_time:.1f}s")
        
    except Exception as e:
        error_message = str(e)
        
        # If server is shutting down (uvicorn --reload), pool-closed errors are expected — exit silently
        if _shutting_down and ("pool" in error_message.lower() and "closed" in error_message.lower()):
            print(f"ℹ️ Thread {thread_id} stopping due to server shutdown (pool closed)")
            return
        
        print(f"❌ Background thread error for thread {thread_id}: {error_message}")
        
        # Check if it's a Google API server error (transient 500)
        is_google_server_error = "500 INTERNAL" in error_message or "ServerError" in error_message or "Internal error encountered" in error_message
        
        if is_google_server_error:
            error_message = "Google's AI servers are temporarily overloaded. Please try again in a moment, or switch to a different model (e.g., Claude or LLaMA)."
        
        # Check if it's a ReadTimeout error
        is_timeout = "Read timeout" in error_message or "ReadTimeoutError" in error_message or "timed out" in error_message.lower()
        
        if is_timeout:
            error_message = "Request timed out. Please try again with a shorter query."
        
        # Check if it's a database/SSL error - reset CRUD pool and provide user-friendly message
        if _is_transient_error(error_message):
            print("🔄 DB/SSL error detected, resetting CRUD pool (checkpointer pool is separate)...")
            try:
                reset_pool()
                print("✅ CRUD pool reset successfully")
            except Exception as reset_e:
                print(f"⚠️ Failed to reset CRUD pool: {reset_e}")
            error_message = "Database connection was interrupted. Please try again."
        elif "ttl_minutes" in error_message:
            error_message = "Database schema issue. Please contact support (missing ttl_minutes column)."
            print("⚠️ FIX: Run 'ALTER TABLE public.store ADD COLUMN IF NOT EXISTS ttl_minutes INTEGER DEFAULT NULL;' in Supabase")
        elif "store" in error_message.lower() and "column" in error_message.lower():
            error_message = "Long-term memory database needs updating. Basic functionality still works."
        
        error_event = {'type': 'error', 'error': error_message}
        store_event(error_event)
        
        update_session_status(thread_id, "error")
        
        # Last-resort: try to salvage any pending downloads to Supabase
        # so they aren't lost after all retries fail
        try:
            from tools.pdftool import get_pending_download as _get_pdf
            from tools.doctool import get_pending_download as _get_docx
            from tools.latextoformate import get_pending_download as _get_latex
            for _get_fn in [_get_pdf, _get_docx, _get_latex]:
                _pending = _get_fn()
                if _pending and _pending.get("data"):
                    download_store.save_to_supabase(
                        thread_id,
                        _pending.get("filename", "download"),
                        _pending["data"]
                    )
                    print(f"  ☁️  Salvaged download to Supabase: {_pending.get('filename')}")
        except Exception as salvage_err:
            print(f"  ⚠️ Download salvage failed: {salvage_err}")
    finally:
        # Cleanup: Remove thread reference and cancellation event
        if thread_id in background_threads:
            del background_threads[thread_id]
        if thread_id in cancellation_events:
            del cancellation_events[thread_id]
        # Don't delete the queue immediately - clients may still be reading


@app.post("/run-agent")
def run_agent(request: AgentRequest, http_request: Request):
    """
    Start the agent in a DETACHED background thread.
    The agent continues running even if the browser disconnects.
    Returns immediately with thread_id, then client subscribes to /threads/{id}/stream.
    """
    # Periodic session cleanup (non-blocking)
    cleanup_old_sessions()
    
    # Validation is handled by Pydantic validators
    if not request.prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    # Get agent from app state (Fix 2: use refreshable instance)
    agent = get_or_refresh_agent()

    # Get or create thread
    thread_id = request.thread_id
    if not thread_id:
        # Require user_id for new thread creation
        if not request.user_id:
            raise HTTPException(status_code=400, detail="user_id is required when creating a new thread")
        
        # Create new thread in both memory and database
        thread = thread_manager.create_thread()
        thread_id = thread.thread_id
        # Save to Supabase
        result = create_thread_for_user(thread_id, request.user_id, thread.title)
        if not result:
            # Check if it failed because user doesn't exist
            if not user_exists(request.user_id):
                raise HTTPException(status_code=400, detail=f"User {request.user_id} does not exist. Please sign in again.")
            raise HTTPException(status_code=500, detail="Failed to create thread in database")
    else:
        # Ensure thread exists in memory cache (it's in Supabase)
        if not thread_manager.thread_exists(thread_id):
            thread_manager._threads[thread_id] = Thread(
                thread_id=thread_id,
                title="Chat"
            )
    
    # Check if a thread is already running for this thread
    current_status = get_session_status(thread_id)
    if current_status == "running":
        # Return existing session info - client should subscribe to stream
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'init', 'thread_id': thread_id, 'status': 'already_running'})}\n\n"]),
            media_type="text/event-stream"
        )
    
    # Update thread title based on first user message
    thread = thread_manager.get_thread(thread_id)
    if thread and thread.title in ["New Chat", "Chat"]:
        # Strip all metadata tags for title generation
        import re
        clean_prompt = re.sub(r'\[(?:UPLOADED_FILES|MODE|PERSONA|SITES|CONSTRAINT|EDIT_META)[:\s][\s\S]*?\]', '', request.prompt).strip()
        if not clean_prompt:
            clean_prompt = "Research Session"
            
        title = clean_prompt[:50] + ("..." if len(clean_prompt) > 50 else "")
        thread_manager.update_thread_title(thread_id, title)
        # Also update in Supabase
        db_update_thread_title(thread_id, title)
    
    # Update timestamp in memory
    thread_manager.update_thread_timestamp(thread_id)
    
    # Configure agent with thread_id and user_id for persistent state + multi-tenant RAG
    config = {
        "configurable": {"thread_id": thread_id, "user_id": request.user_id or ""},
        "recursion_limit": 100  # Hard cap on agent steps to prevent infinite loops
    }
    if request.parent_checkpoint_id:
        config["configurable"]["checkpoint_id"] = request.parent_checkpoint_id

    # Initialize session tracking
    init_session(thread_id, {
        "status": "running",
        "events": [],
        "last_content": "",
        "prompt": request.prompt,
        "deep_research": request.deep_research,
        "literature_survey": request.literature_survey,
        "sites": request.sites or [],
        "started_at": datetime.now().isoformat()
    })
    
    # Create message queue for this session
    message_queues[thread_id] = queue.Queue(maxsize=1000)
    
    # Build edit metadata if this is an edit operation
    edit_metadata = None
    if request.edit_group_id:
        edit_metadata = {
            "edit_group_id": request.edit_group_id,
            "edit_version": request.edit_version,
            "original_message_index": request.original_message_index
        }
    
    # START DETACHED BACKGROUND THREAD
    bg_thread = threading.Thread(
        target=run_agent_background,
        args=(agent, thread_id, request.prompt, config, request.deep_research, request.literature_survey, request.persona, edit_metadata, request.sites, request.user_id),
        daemon=True
    )
    bg_thread.start()
    background_threads[thread_id] = bg_thread
    
    # Return SSE stream that reads from the queue
    def event_generator():
        """Stream events from the background thread to the client"""
        try:
            q = message_queues.get(thread_id)
            if not q:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Queue not found'})}\n\n"
                return
            
            # Stream events until done or error
            while True:
                try:
                    # Wait for next event with timeout
                    event = q.get(timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    # Stop on all terminal conditions
                    if event.get('type') in ('done', 'error', 'cancelled'):
                        break
                except queue.Empty:
                    # Check session status directly if queue is quiet
                    status = get_session_status(thread_id)
                    if status in ("completed", "error", "cancelled"):
                        break
                    
                    # Send keepalive ping
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        except Exception as e:
            # Client disconnected - that's OK, background thread continues!
            print(f"📡 Client disconnected from stream for thread {thread_id} - background thread continues: {e}")
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _serialize_message(msg) -> Optional[Dict[str, Any]]:
    """Helper function to serialize a message to dict"""
    try:
        if hasattr(msg, "model_dump"):
            data = msg.model_dump()
        elif hasattr(msg, "dict"):
            data = msg.dict()
        elif hasattr(msg, "content"):
            data = {
                "content": msg.content,
                "type": getattr(msg, "type", "ai"),
                "role": getattr(msg, "role", "assistant")
            }
        elif isinstance(msg, dict):
            data = msg
        else:
            data = {"content": str(msg), "type": "unknown"}
        
        content = data.get("content")
        msg_type = data.get("type", "unknown")
        msg_role = data.get("role", "unknown")

        # FILTER: Only show AI content. Hide Tool/Function outputs from the UI stream.
        # Exception: Keep download markers which are passed via tool outputs.
        if msg_type in ["tool", "function"] or msg_role in ["tool", "function"]:
            if isinstance(content, str) and ("[DOWNLOAD_DOCX]" in content or "[DOWNLOAD_PDF]" in content or "[DOWNLOAD_MD]" in content):
                # Keep download data
                pass 
            else:
                # hide raw tool output (JSON, search results, etc.)
                content = ""

        if isinstance(content, str):
            # Strip internal markers for a clean UI
            import re
            content = re.sub(r'\[MODE:.*?\]', '', content)
            content = re.sub(r'\[SUBAGENT:.*?\]', '', content)
            content = re.sub(r'\[SITES:.*?\]', '', content)
            content = re.sub(r'\[RESTRICT_SEARCH:.*?\]', '', content)
            
            # Strip download markers from AI messages (they're sent via separate 'download' events now)
            # This prevents corrupted/truncated base64 from appearing in the UI
            if msg_type not in ["tool", "function"] and msg_role not in ["tool", "function"]:
                # First, try to extract and send download data if present (fallback for when tool interception missed it)
                for marker in ["[DOWNLOAD_PDF]", "[DOWNLOAD_DOCX]", "[DOWNLOAD_MD]"]:
                    if marker in content:
                        try:
                            marker_idx = content.index(marker)
                            json_start = content.index("{", marker_idx)
                            # Find matching closing brace using brace counting
                            brace_count = 0
                            json_end = json_start
                            for i, char in enumerate(content[json_start:], json_start):
                                if char == '{':
                                    brace_count += 1
                                elif char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        json_end = i
                                        break
                            # Remove the marker and JSON from content
                            content = content[:marker_idx] + content[json_end + 1:]
                        except (ValueError, IndexError):
                            # If parsing fails, just strip everything after marker
                            content = re.sub(r'\[DOWNLOAD_PDF\].*$', '', content, flags=re.DOTALL)
                            content = re.sub(r'\[DOWNLOAD_DOCX\].*$', '', content, flags=re.DOTALL)
                            content = re.sub(r'\[DOWNLOAD_MD\].*$', '', content, flags=re.DOTALL)
            
            content = content.strip()
        elif isinstance(content, list):
            # Handle Gemini array format: [{"text": "..."}]
            import re
            parts = []
            for item in content:
                if isinstance(item, dict) and 'text' in item:
                    text = item['text']
                    # Strip internal markers
                    text = re.sub(r'\[MODE:.*?\]', '', text)
                    text = re.sub(r'\[SUBAGENT:.*?\]', '', text)
                    text = re.sub(r'\[SITES:.*?\]', '', text)
                    text = re.sub(r'\[RESTRICT_SEARCH:.*?\]', '', text)
                    # Strip download markers from AI messages
                    if msg_type not in ["tool", "function"] and msg_role not in ["tool", "function"]:
                        for marker in ["[DOWNLOAD_PDF]", "[DOWNLOAD_DOCX]", "[DOWNLOAD_MD]"]:
                            if marker in text:
                                try:
                                    marker_idx = text.index(marker)
                                    json_start = text.index("{", marker_idx)
                                    brace_count = 0
                                    json_end = json_start
                                    for i, char in enumerate(text[json_start:], json_start):
                                        if char == '{':
                                            brace_count += 1
                                        elif char == '}':
                                            brace_count -= 1
                                            if brace_count == 0:
                                                json_end = i
                                                break
                                    text = text[:marker_idx] + text[json_end + 1:]
                                except (ValueError, IndexError):
                                    text = re.sub(r'\[DOWNLOAD_PDF\].*$', '', text, flags=re.DOTALL)
                                    text = re.sub(r'\[DOWNLOAD_DOCX\].*$', '', text, flags=re.DOTALL)
                                    text = re.sub(r'\[DOWNLOAD_MD\].*$', '', text, flags=re.DOTALL)
                    parts.append(text.strip())
            content = ''.join(parts).strip()

        # Extract edit metadata from additional_kwargs if present
        additional_kwargs = data.get("additional_kwargs", {})
        edit_group_id = additional_kwargs.get("edit_group_id")
        edit_version = additional_kwargs.get("edit_version")
        is_edit = additional_kwargs.get("is_edit", False)
        original_message_index = additional_kwargs.get("original_message_index")

        # Ensure tool_calls and name are included for UI status display
        result = {
            "type": data.get("type"),
            "content": content,
            "tool_calls": data.get("tool_calls", []),
            "name": data.get("name"),
            "role": data.get("role")
        }
        
        # Include edit metadata if present
        if edit_group_id:
            result["edit_group_id"] = edit_group_id
            result["edit_version"] = edit_version
            result["is_edit"] = is_edit
            result["original_message_index"] = original_message_index
        
        return result
    except Exception:
        return None


def _serialize_chunk(chunk) -> Optional[Dict[str, Any]]:
    """Serialize a stream chunk for SSE transmission"""
    try:
        result = {"type": "update"}
        messages = []
        
        for key, value in chunk.items():
            # Skip non-iterable objects like Overwrite
            if hasattr(value, '__class__') and value.__class__.__name__ == 'Overwrite':
                # Handle Overwrite object - extract the actual value
                if hasattr(value, 'value'):
                    value = value.value
                else:
                    continue
            
            raw_messages = []
            if key == "messages":
                # Direct messages list - check if iterable
                if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                    raw_messages.extend(value)
                elif hasattr(value, 'content'):
                    raw_messages.append(value)
            elif isinstance(value, dict) and "messages" in value:
                msg_list = value["messages"]
                if hasattr(msg_list, '__iter__') and not isinstance(msg_list, (str, bytes)):
                    raw_messages.extend(msg_list)
            elif isinstance(value, list):
                for item in value:
                    if hasattr(item, "content") or (isinstance(item, dict) and "content" in item):
                        raw_messages.append(item)
            
            # Only serialize the LAST message from this node to avoid replaying history
            # LangGraph updates mode can include full message list; we only want the newest
            if raw_messages:
                # Take only the last message (the newest output)
                last_msg = raw_messages[-1]
                serialized = _serialize_message(last_msg)
                if serialized:
                    messages.append(serialized)
        
        if messages:
            result["messages"] = messages
            return result
        return None
    except Exception as e:
        print(f"DEBUG SERIALIZE ERROR: {e}")
        return None


# -----------------------------
# Paper Writer Chat Endpoint
# -----------------------------

class PaperWriterChatRequest(BaseModel):
    message: str
    session_id: str = "default-session"
    paper_content: Optional[str] = None
    chat_history: Optional[list] = None

@app.post("/paper-writer/chat")
def paper_writer_chat(request: PaperWriterChatRequest):
    """AI assistant for modifying LaTeX paper templates."""
    try:
        from paper_writer.writer import process_writer_request
        
        result = process_writer_request(
            message=request.message,
            paper_content=request.paper_content,
            chat_history=request.chat_history
        )
        
        return {
            "response": result["response"],
            "updated_latex": result.get("updated_latex"),
            "change_type": result.get("change_type", "info"),
            "success": result.get("success", True)
        }
    except Exception as e:
        print(f"Paper Writer Error: {e}")
        return {
            "response": f"Sorry, I encountered an error: {str(e)}",
            "updated_latex": None,
            "change_type": "error",
            "success": False
        }


# -----------------------------
# Local Run
# -----------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
