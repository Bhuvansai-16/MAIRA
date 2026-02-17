# Backend for MAIRA Deep Research Agent
# Synchronous version - no async/await patterns

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from main_agent import agent, prompt_v2, subagents, tools, checkpointer
from deepagents import create_deep_agent
import database as _db
from database import (
    pool, 
    reset_pool,
    validate_pool,
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
from datetime import datetime
import json
import uuid
from collections import defaultdict
import threading
import queue
import time
import download_store

# Active session tracking for reconnection support
# Stores: thread_id -> {"status": "running"|"completed"|"error", "events": [], "last_content": str, "prompt": str}
active_sessions: Dict[str, Dict[str, Any]] = {}
session_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)

# Message queues for real-time streaming to connected clients
# thread_id -> queue.Queue
message_queues: Dict[str, queue.Queue] = {}

# Background thread references
background_threads: Dict[str, threading.Thread] = {}

app = FastAPI(title="MAIRA – Deep Research Agent")

# Apply lifespan manually using startup/shutdown events
@app.on_event("startup")
def startup_event():
    # 1. Pool is already opened in main_agent.py when importing agent
    
    # 2. Validate pool health on startup
    if not validate_pool():
        print("⚠️ Pool unhealthy on startup, resetting...")
        reset_pool()
    
    # 3. Ensure default user exists (required for thread foreign key)
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
    
    # 4. Set agent directly (already initialized in main_agent.py)
    app.state.agent = agent
    print("✅ MAIRA Agent ready")


@app.on_event("shutdown")
def shutdown_event():
    _db.pool.close()
    _db._checkpointer_pool.close()
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
    """Production health check — verifies DB pool connectivity."""
    db_ok = validate_pool()
    pool_stats = {
        "min_size": _db.pool.min_size,
        "max_size": _db.pool.max_size,
    }
    try:
        pool_stats["size"] = _db.pool.get_stats().get("pool_size", "N/A")
        pool_stats["idle"] = _db.pool.get_stats().get("pool_available", "N/A")
    except Exception:
        pass

    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "database": "connected" if db_ok else "disconnected",
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
# Health Check Endpoint
# -----------------------------

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "MAIRA Deep Research Agent"}


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

    agent = http_request.app.state.agent
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

            vision_model = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash", temperature=0)
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
    
    # Recreate the main agent with the new model
    try:
        new_model = get_model_instance(request.model_key)
        
        # KEY FIX: Update SUBAGENTS to use the new subagent_model from config
        # This ensures subagents switch model according to the logic in config.py
        current_subagent_model = config.subagent_model
        
        # Iterate through the subagents list (imported from main_agent) and update their model
        for subagent_config in subagents:
            if isinstance(subagent_config, dict) and "model" in subagent_config:
                subagent_config["model"] = current_subagent_model
                
        # Recreate main agent with new model and UPDATED subagents
        http_request.app.state.agent = create_deep_agent(
            subagents=subagents,  # Now contains updated models
            model=new_model,
            tools=tools,
            system_prompt=prompt_v2,
            checkpointer=checkpointer,
        )
        
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
        agent = request.app.state.agent
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
        agent = request.app.state.agent
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
        agent = request.app.state.agent
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
        agent = http_request.app.state.agent
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
        agent = request.app.state.agent
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
def get_session_status(thread_id: str):
    """Get the status of an active agent session for reconnection support"""
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
    Sets a cancellation flag that the background thread checks during execution.
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
    
    # Set the cancellation flag
    session["cancelled"] = True
    session["status"] = "cancelled"
    
    # Send cancellation event to any connected clients
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
    if thread_id not in active_sessions:
        raise HTTPException(status_code=404, detail="No active session found")
    
    session = active_sessions[thread_id]
    
    def reconnect_generator():
        try:
            # 1. First, replay all buffered events from the requested index
            events = session.get("events", [])
            for i, event in enumerate(events[from_index:], start=from_index):
                yield f"data: {json.dumps({**event, 'replayed': True, 'index': i})}\n\n"
            
            last_sent = len(events)
            
            # 2. If session is still running, poll the queue for live updates
            if session.get("status") == "running":
                q = message_queues.get(thread_id)
                
                if q:
                    while session.get("status") == "running":
                        try:
                            event = q.get(timeout=30.0)
                            yield f"data: {json.dumps(event)}\n\n"
                            
                            if event.get('type') in ('done', 'error'):
                                break
                        except queue.Empty:
                            # Send keepalive and check status
                            yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                            if session.get("status") != "running":
                                break
                else:
                    # No queue, poll the events buffer
                    while session.get("status") == "running":
                        time.sleep(0.1)
                        current_events = session.get("events", [])
                        if len(current_events) > last_sent:
                            for i, event in enumerate(current_events[last_sent:], start=last_sent):
                                yield f"data: {json.dumps({**event, 'index': i})}\n\n"
                            last_sent = len(current_events)
            
            # 3. Send final status
            yield f"data: {json.dumps({'type': 'reconnect_complete', 'status': session.get('status')})}\n\n"
            
        except Exception as e:
            # Client disconnected during reconnect
            print(f"📡 Client disconnected during reconnect for thread {thread_id}: {e}")
    
    return StreamingResponse(reconnect_generator(), media_type="text/event-stream")


# -----------------------------
# Agent Endpoint
# -----------------------------

# Maximum retries for transient DB/SSL errors during streaming
_MAX_STREAM_RETRIES = 3


def _stream_with_retry(agent, stream_input, config, thread_id, store_event):
    """
    Generator that wraps agent.stream() with automatic retry on transient
    database/SSL errors.  The checkpointer uses its own dedicated pool
    (never reset), so we just wait for its built-in health checks to
    discard bad connections, then retry from the last LangGraph checkpoint.
    """
    attempt = 0
    current_input = stream_input

    while attempt <= _MAX_STREAM_RETRIES:
        try:
            yield from agent.stream(
                current_input,
                config=config,
                stream_mode="updates"
            )
            return  # Stream completed successfully

        except Exception as e:
            error_msg = str(e)
            if _is_transient_error(error_msg) and attempt < _MAX_STREAM_RETRIES:
                attempt += 1
                print(f"🔄 Stream retry {attempt}/{_MAX_STREAM_RETRIES} for thread {thread_id}: {error_msg}")
                
                # Fully reset the checkpointer pool — the SSL connection is dead.
                # A simple health check is not enough; the dead connection may be
                # the one LangGraph's PostgresSaver uses internally.
                try:
                    from database import reset_checkpointer_pool, _checkpointer_pool, get_checkpointer
                    reset_checkpointer_pool()
                    
                    # Reinitialize the checkpointer with the fresh pool
                    new_checkpointer = get_checkpointer()
                    
                    # Update the agent's checkpointer so retries use the fresh pool
                    # LangGraph compiled graphs store checkpointer internally
                    if hasattr(agent, 'checkpointer'):
                        agent.checkpointer = new_checkpointer
                    
                    print(f"   ✅ Checkpointer fully reset and reinitialized")
                except Exception as pool_err:
                    print(f"   ⚠️ Checkpointer pool reset failed: {pool_err}")
                
                time.sleep(min(3 * attempt, 10))

                # Notify frontend
                store_event({'type': 'content', 'messages': [{
                    'role': 'assistant',
                    'content': '\n\n> ⚠️ Database connection interrupted. Reconnecting...\n\n'
                }]})

                # Resume from last checkpoint — don't re-send user message
                current_input = None
                continue

            raise  # Non-transient or retries exhausted — propagate to caller


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
    sent_content_hashes = set()  # Track content already sent to prevent duplicates
    
    # Mapping of tool/agent names to user-friendly status messages
    TOOL_STATUS_MESSAGES = {
        # Subagents (called via 'task' tool)
        'write_todos': {'start': '📅 Planning research...', 'complete': 'Plan created'},
        'github-agent': {'start': '🐙 Analyzing GitHub repo...', 'complete': 'Repo analysis complete'},
        'websearch-agent': {'start': '🌐 Searching the web...', 'complete': 'Web search complete'},
        'academic-paper-agent': {'start': '📚 Searching for research papers...', 'complete': 'Paper search complete'},
        'draft-subagent': {'start': '✍️ Drafting results...', 'complete': 'Draft complete'},
        'deep-reasoning-agent': {'start': '🧠 Deep verification...', 'complete': 'Verification complete'},
        'summary-subagent': {'start': '📝 Summarizing findings...', 'complete': 'Summary complete'},
        'report-subagent': {'start': '📄 Generating report...', 'complete': 'Report generated'},
        # Direct tools
        'internet_search': {'start': '🔍 Performing web search...', 'complete': 'Search complete'},
        'arxiv_search': {'start': '📖 Searching arXiv papers...', 'complete': 'arXiv search complete'},
        'export_to_pdf': {'start': '📑 Exporting to PDF...', 'complete': 'PDF exported'},
        'export_to_docx': {'start': '📝 Exporting to DOCX...', 'complete': 'DOCX exported'},
        'extract_content': {'start': '📄 Extracting content...', 'complete': 'Content extracted'},
        'literature-survey-agent': {'start': '📚 Conducting literature survey...', 'complete': 'Literature survey complete'},
        # LaTeX conversion tools
        'convert_latex_to_pdf': {'start': '📑 Converting to PDF...', 'complete': 'PDF conversion complete'},
        'convert_latex_to_docx': {'start': '📝 Converting to DOCX...', 'complete': 'DOCX conversion complete'},
        'convert_latex_to_markdown': {'start': '📄 Converting to Markdown...', 'complete': 'Markdown conversion complete'},
        'convert_latex_to_all_formats': {'start': '📚 Converting to all formats...', 'complete': 'Conversions complete'},
        'generate_and_convert_document': {'start': '📝 Generating document...', 'complete': 'Document generated'},
        'generate_large_document_with_chunks': {'start': '📚 Generating large document...', 'complete': 'Document generated'},
        'search_knowledge_base': {'start': '🔍 Searching uploaded documents...', 'complete': 'Document search complete'},
    }
    
    # Progress mapping (0-100)
    TOOL_PROGRESS = {
        'write_todos': 10,
        'github-agent': 15,
        'search_knowledge_base': 15,
        'websearch-agent': 30,
        'academic-paper-agent': 40,
        'draft-subagent': 60,
        'deep-reasoning-agent': 75,
        'summary-subagent': 90,
        'report-subagent': 95,
        'literature-survey-agent': 50,
        'internet_search': 25,
    }
    
    def store_event(event_data: dict):
        """Store event in session buffer and push to queue"""
        nonlocal event_counter
        event_counter += 1
        event_data['event_id'] = f'{thread_id}_{event_counter}'
        
        if thread_id in active_sessions:
            active_sessions[thread_id]["events"].append(event_data)
            # Update last content if it's a content update
            if event_data.get("messages"):
                for msg in event_data["messages"]:
                    if msg.get("content"):
                        active_sessions[thread_id]["last_content"] = msg["content"]
        
        # Push to queue for any connected clients
        if thread_id in message_queues:
            try:
                message_queues[thread_id].put_nowait(event_data)
            except queue.Full:
                pass  # Queue full, event is still stored in buffer
    
    def get_status_message(tool_name: str, step: str) -> str:
        """Get user-friendly status message for a tool"""
        if tool_name in TOOL_STATUS_MESSAGES:
            return TOOL_STATUS_MESSAGES[tool_name].get(step, f'{tool_name}...')
        return f'Running {tool_name}...' if step == 'start' else f'Finished {tool_name}'
    
    try:
        # Send init event
        init_event = {'thread_id': thread_id, 'type': 'init'}
        store_event(init_event)
        
        # Buffer to hold download events - sent AFTER all content to keep summary + download in sync
        buffered_download_event = None
        download_marker_seen = False
        
        # Prefix message with mode indicator for agent routing
        # Also include persona context
        if literature_survey:
            mode_prefix = "[MODE: LITERATURE_SURVEY] "
        elif deep_research:
            mode_prefix = "[MODE: DEEP_RESEARCH] "
        else:
            mode_prefix = "[MODE: CHAT] "
        
        # Add persona instruction - ALWAYS include it for agent awareness
        persona_instruction = ""
        persona_value = persona.lower() if persona else "default"
        
        print(f"🚀 Background thread started for thread {thread_id}")
        print(f"   📋 Persona received: '{persona}' (type: {type(persona).__name__})")
        print(f"   🔍 Deep Research: {deep_research}")
        print(f"   📚 Literature Survey: {literature_survey}")
        
        if not literature_survey:
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
        
        # Stream agent updates with automatic retry on transient DB/SSL errors
        for chunk in _stream_with_retry(
            agent,
            {"messages": [message_input]},
            config, thread_id, store_event
        ):
            # CHECK FOR CANCELLATION at the start of each chunk
            if thread_id in active_sessions and active_sessions[thread_id].get("cancelled"):
                print(f"🛑 Cancellation detected for thread {thread_id}, stopping agent...")
                cancelled_event = {'type': 'cancelled', 'message': 'Generation stopped by user'}
                store_event(cancelled_event)
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
                                
                                # If it's a subagent call via 'task' tool, get the actual agent name
                                if tool_name == "task":
                                    display_name = tool_args.get("name", "subagent") if isinstance(tool_args, dict) else "subagent"
                                else:
                                    display_name = tool_name
                                
                                if display_name and display_name not in active_tools:
                                    active_tools.add(display_name)
                                    progress_val = TOOL_PROGRESS.get(display_name)
                                    
                                    status_event = {
                                        "type": "status",
                                        "step": "start",
                                        "agent": node_name,
                                        "tool": display_name,
                                        "message": get_status_message(display_name, "start"),
                                        "progress": progress_val
                                    }
                                    store_event(status_event)
                                    print(f"  🔧 [{node_name}] Starting: {display_name}")
                        
                        # 2. Detect TOOL COMPLETION - when tool returns result
                        msg_type = getattr(msg, "type", None) or (msg.get("type") if isinstance(msg, dict) else None)
                        msg_name = getattr(msg, "name", None) or (msg.get("name") if isinstance(msg, dict) else None)
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
                        
                        if msg_type == "tool" and msg_name:
                            if msg_name in active_tools:
                                active_tools.discard(msg_name)
                                status_event = {
                                    "type": "status",
                                    "step": "complete",
                                    "tool": msg_name,
                                    "message": get_status_message(msg_name, "complete")
                                }
                                store_event(status_event)
                                print(f"  ✅ Tool complete: {msg_name}")
            
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
                
                # Check for reasoning/thinking blocks in content
                if serialized.get('messages'):
                    # Only check the last message for new reasoning to avoid reprocessing history
                    msgs = serialized['messages']
                    # Process only the last message if it exists
                    msg_list_to_check = [msgs[-1]] if msgs else []
                    
                    for msg in msg_list_to_check:
                        content = msg.get('content', '')
                        if isinstance(content, str) and '<think>' in content:
                            # Extract and send reasoning separately
                            think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
                            if think_match:
                                reasoning = think_match.group(1).strip()
                                reasoning_event = {'type': 'reasoning', 'content': reasoning}
                                store_event(reasoning_event)
                                # Clean the content
                                msg['content'] = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                
                store_event(serialized)
        
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
        
        # Send completion event with final checkpoint ID
        final_state = agent.get_state(config)
        checkpoint_id = final_state.config["configurable"].get("checkpoint_id", "") if final_state else ""
        done_event = {'type': 'done', 'checkpoint_id': checkpoint_id}
        store_event(done_event)
        
        # Mark session as completed
        if thread_id in active_sessions:
            active_sessions[thread_id]["status"] = "completed"
        
        print(f"✅ Background thread completed for thread {thread_id}")
        
    except Exception as e:
        error_message = str(e)
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
        
        if thread_id in active_sessions:
            active_sessions[thread_id]["status"] = "error"
        
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
        # Cleanup: Remove thread reference
        if thread_id in background_threads:
            del background_threads[thread_id]
        # Don't delete the queue immediately - clients may still be reading


@app.post("/run-agent")
def run_agent(request: AgentRequest, http_request: Request):
    """
    Start the agent in a DETACHED background thread.
    The agent continues running even if the browser disconnects.
    Returns immediately with thread_id, then client subscribes to /threads/{id}/stream.
    """
    if not request.prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    # Get agent from app state
    agent = http_request.app.state.agent

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
    if thread_id in active_sessions and active_sessions[thread_id].get("status") == "running":
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
        "recursion_limit": 50  # Hard cap on agent steps to prevent infinite loops
    }
    if request.parent_checkpoint_id:
        config["configurable"]["checkpoint_id"] = request.parent_checkpoint_id

    # Initialize session tracking
    active_sessions[thread_id] = {
        "status": "running",
        "events": [],
        "last_content": "",
        "prompt": request.prompt,
        "deep_research": request.deep_research,
        "literature_survey": request.literature_survey,
        "sites": request.sites or [],
        "started_at": datetime.now().isoformat()
    }
    
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
                    status = active_sessions.get(thread_id, {}).get("status")
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
