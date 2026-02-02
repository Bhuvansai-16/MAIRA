# CRITICAL: Force SelectorEventLoop for psycopg async compatibility on Windows
# This MUST be at the very top before any other imports
import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# NOW import other modules
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from main_agent import pool, get_checkpointer, create_agent, research_prompt, subagents, tools
from thread_manager import thread_manager, Thread, CheckpointInfo
from datetime import datetime

# Load existing threads from database on import
thread_manager.load_from_db()
import json
import uuid
from contextlib import asynccontextmanager
from collections import defaultdict

# Active session tracking for reconnection support
# Stores: thread_id -> {"status": "running"|"completed"|"error", "events": [], "last_content": str, "prompt": str}
active_sessions: Dict[str, Dict[str, Any]] = {}
session_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

# Message queues for real-time streaming to connected clients
# thread_id -> asyncio.Queue
message_queues: Dict[str, asyncio.Queue] = {}

# Background task references to prevent garbage collection
background_tasks: Dict[str, asyncio.Task] = {}

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Open the async connection pool
    await pool.open()
    print("✅ Database connection pool opened")
    
    # 2. Setup checkpointer (creates tables automatically if they don't exist)
    checkpointer = await get_checkpointer()
    print("✅ AsyncPostgresSaver checkpointer ready - tables created/verified")
    
    # 3. Create the agent with the async checkpointer
    app.state.agent = await create_agent(checkpointer)
    app.state.checkpointer = checkpointer
    print("✅ MAIRA Agent initialized and ready")
    
    yield
    
    # 4. Cleanup on shutdown
    await pool.close()
    print("✅ Database connection pool closed")

app = FastAPI(
    title="MAIRA – Deep Research Agent",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# Helper function to get agent from app state
def get_agent(request: Request):
    return request.app.state.agent


# -----------------------------
# Request Schemas
# -----------------------------

class AgentRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = None  # If not provided, creates new thread
    deep_research: bool = False  # When True, enables full Tier 3 research workflow
    parent_checkpoint_id: Optional[str] = None  # For branching from a specific checkpoint
    last_event_id: Optional[str] = None  # For stream reconnection


class CreateThreadRequest(BaseModel):
    title: Optional[str] = None


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


# -----------------------------
# Health Check Endpoint
# -----------------------------

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "MAIRA Deep Research Agent"}


@app.get("/db-test")
async def test_database(request: Request):
    """Test database connection with a simple HI message"""
    try:
        agent = request.app.state.agent
        test_thread_id = f"test-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": test_thread_id}}
        
        # Run a simple "HI" through the agent
        result = await agent.ainvoke(
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
async def create_thread(request: CreateThreadRequest = None):
    """Create a new conversation thread with UUID v7"""
    title = request.title if request else None
    thread = thread_manager.create_thread(title=title)
    return thread.to_dict()


@app.get("/threads", response_model=List[Dict[str, Any]])
async def list_threads():
    """Get all conversation threads, sorted by newest first"""
    threads = thread_manager.get_all_threads()
    return [t.to_dict() for t in threads]


@app.get("/threads/{thread_id}", response_model=Dict[str, Any])
async def get_thread(thread_id: str):
    """Get a specific thread by ID"""
    thread = thread_manager.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread.to_dict()


@app.put("/threads/{thread_id}", response_model=Dict[str, Any])
async def update_thread(thread_id: str, request: UpdateThreadRequest):
    """Update thread title"""
    thread = thread_manager.update_thread_title(thread_id, request.title)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread.to_dict()


@app.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a thread"""
    if not thread_manager.delete_thread(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"status": "deleted", "thread_id": thread_id}


@app.get("/threads/{thread_id}/messages", response_model=Dict[str, Any])
async def get_thread_messages(thread_id: str, request: Request):
    """Get all messages for a specific thread"""
    try:
        agent = request.app.state.agent
        # Get state from checkpointer using thread_id config
        config = {"configurable": {"thread_id": thread_id}}
        state = await agent.aget_state(config)
        
        # If thread exists in checkpointer but not in thread_manager, create it
        if state and state.values and not thread_manager.thread_exists(thread_id):
            thread_manager._threads[thread_id] = Thread(
                thread_id=thread_id,
                title="Recovered Chat"
            )
            thread_manager.save_to_db()
        
        messages = []
        if state and state.values and "messages" in state.values:
            for msg in state.values["messages"]:
                msg_data = _serialize_message(msg)
                if msg_data:
                    messages.append(msg_data)
        
        return {"thread_id": thread_id, "messages": messages}
    except Exception as e:
        return {"thread_id": thread_id, "messages": [], "error": str(e)}


# -----------------------------
# History & Branching Endpoints
# -----------------------------

@app.get("/threads/{thread_id}/history", response_model=Dict[str, Any])
async def get_thread_history(thread_id: str, request: Request):
    """Get checkpoint history for time travel functionality"""
    if not thread_manager.thread_exists(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    
    try:
        agent = request.app.state.agent
        config = {"configurable": {"thread_id": thread_id}}
        checkpoints = []
        
        # Use LangGraph's get_state_history for time travel (async version)
        async for state in agent.aget_state_history(config):
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
async def branch_from_checkpoint(thread_id: str, request: BranchRequest, http_request: Request):
    """Create a new branch from a specific checkpoint (fork conversation)"""
    if not thread_manager.thread_exists(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    
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
        
        source_state = await agent.aget_state(source_config)
        
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
async def get_checkpoint_state(thread_id: str, checkpoint_id: str, request: Request):
    """Get the state at a specific checkpoint for time travel preview"""
    if not thread_manager.thread_exists(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    
    try:
        agent = request.app.state.agent
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id
            }
        }
        
        state = await agent.aget_state(config)
        
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
async def get_session_status(thread_id: str):
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
async def get_session_events(thread_id: str, from_index: int = 0):
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


@app.get("/sessions/{thread_id}/stream")
async def reconnect_session_stream(thread_id: str, from_index: int = 0):
    """
    Reconnect to an active session's event stream.
    First replays all buffered events, then streams live updates.
    """
    if thread_id not in active_sessions:
        raise HTTPException(status_code=404, detail="No active session found")
    
    session = active_sessions[thread_id]
    
    async def reconnect_generator():
        try:
            # 1. First, replay all buffered events from the requested index
            events = session.get("events", [])
            for i, event in enumerate(events[from_index:], start=from_index):
                yield f"data: {json.dumps({**event, 'replayed': True, 'index': i})}\n\n"
            
            last_sent = len(events)
            
            # 2. If session is still running, subscribe to the queue for live updates
            if session.get("status") == "running":
                queue = message_queues.get(thread_id)
                
                if queue:
                    while session.get("status") == "running":
                        try:
                            event = await asyncio.wait_for(queue.get(), timeout=30.0)
                            yield f"data: {json.dumps(event)}\n\n"
                            
                            if event.get('type') in ('done', 'error'):
                                break
                        except asyncio.TimeoutError:
                            # Send keepalive and check status
                            yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                            if session.get("status") != "running":
                                break
                else:
                    # No queue, poll the events buffer
                    while session.get("status") == "running":
                        await asyncio.sleep(0.1)
                        current_events = session.get("events", [])
                        if len(current_events) > last_sent:
                            for i, event in enumerate(current_events[last_sent:], start=last_sent):
                                yield f"data: {json.dumps({**event, 'index': i})}\n\n"
                            last_sent = len(current_events)
            
            # 3. Send final status
            yield f"data: {json.dumps({'type': 'reconnect_complete', 'status': session.get('status')})}\n\n"
            
        except asyncio.CancelledError:
            # Client disconnected during reconnect - background task continues
            print(f"📡 Client disconnected during reconnect for thread {thread_id}")
            pass
    
    return StreamingResponse(reconnect_generator(), media_type="text/event-stream")


# -----------------------------
# Agent Endpoint
# -----------------------------

async def run_agent_background(agent, thread_id: str, prompt: str, config: dict, deep_research: bool):
    """
    DETACHED BACKGROUND TASK: Runs the agent independently of HTTP connection.
    This task continues even if the browser reloads or disconnects.
    """
    import re
    event_counter = 0
    active_tools = set()  # Track active tools to send completion events
    
    # Mapping of tool/agent names to user-friendly status messages
    TOOL_STATUS_MESSAGES = {
        # Subagents (called via 'task' tool)
        'websearch-agent': {'start': '🌐 Searching the web...', 'complete': 'Web search complete'},
        'academic-paper-agent': {'start': '📚 Searching for research papers...', 'complete': 'Paper search complete'},
        'draft-subagent': {'start': '✍️ Drafting results...', 'complete': 'Draft complete'},
        'deep-reasoning-agent': {'start': '🧠 Analyzing and verifying...', 'complete': 'Analysis complete'},
        'report-subagent': {'start': '📄 Generating report...', 'complete': 'Report generated'},
        # Direct tools
        'internet_search': {'start': '🔍 Performing web search...', 'complete': 'Search complete'},
        'arxiv_search': {'start': '📖 Searching arXiv papers...', 'complete': 'arXiv search complete'},
        'export_to_pdf': {'start': '📑 Exporting to PDF...', 'complete': 'PDF exported'},
        'export_to_docx': {'start': '📝 Exporting to DOCX...', 'complete': 'DOCX exported'},
        'extract_content': {'start': '📄 Extracting content...', 'complete': 'Content extracted'},
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
            except asyncio.QueueFull:
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
        
        # Prefix message with mode indicator for agent routing
        mode_prefix = "[MODE: DEEP_RESEARCH] " if deep_research else "[MODE: CHAT] "
        user_content = mode_prefix + prompt
        
        print(f"🚀 Background task started for thread {thread_id}")
        
        # Stream agent updates - this runs independently of HTTP connection
        async for chunk in agent.astream(
            {"messages": [{"role": "user", "content": user_content}]},
            config=config,
            stream_mode="updates"
        ):
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
                                    status_event = {
                                        "type": "status",
                                        "step": "start",
                                        "agent": node_name,
                                        "tool": display_name,
                                        "message": get_status_message(display_name, "start")
                                    }
                                    store_event(status_event)
                                    print(f"  🔧 [{node_name}] Starting: {display_name}")
                        
                        # 2. Detect TOOL COMPLETION - when tool returns result
                        msg_type = getattr(msg, "type", None) or (msg.get("type") if isinstance(msg, dict) else None)
                        msg_name = getattr(msg, "name", None) or (msg.get("name") if isinstance(msg, dict) else None)
                        
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
                # Check for reasoning/thinking blocks in content
                if serialized.get('messages'):
                    for msg in serialized['messages']:
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
        
        # Send completion event with final checkpoint ID
        final_state = await agent.aget_state(config)
        checkpoint_id = final_state.config["configurable"].get("checkpoint_id", "") if final_state else ""
        done_event = {'type': 'done', 'checkpoint_id': checkpoint_id}
        store_event(done_event)
        
        # Mark session as completed
        if thread_id in active_sessions:
            active_sessions[thread_id]["status"] = "completed"
        
        print(f"✅ Background task completed for thread {thread_id}")
        
    except asyncio.CancelledError:
        # Task was cancelled (server shutdown)
        print(f"⚠️ Background task cancelled for thread {thread_id}")
        if thread_id in active_sessions:
            active_sessions[thread_id]["status"] = "cancelled"
        raise
    except Exception as e:
        error_message = str(e)
        print(f"❌ Background task error for thread {thread_id}: {error_message}")
        
        # Check if it's a database/SSL error - provide user-friendly message
        if "SSL" in error_message or "connection" in error_message.lower():
            error_message = "Database connection was interrupted. Please try again."
        
        error_event = {'type': 'error', 'error': error_message}
        store_event(error_event)
        
        if thread_id in active_sessions:
            active_sessions[thread_id]["status"] = "error"
    finally:
        # Cleanup: Remove task reference and close queue
        if thread_id in background_tasks:
            del background_tasks[thread_id]
        # Don't delete the queue immediately - clients may still be reading


@app.post("/run-agent")
async def run_agent(request: AgentRequest, http_request: Request):
    """
    Start the agent in a DETACHED background task.
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
        thread = thread_manager.create_thread()
        thread_id = thread.thread_id
    elif not thread_manager.thread_exists(thread_id):
        thread = thread_manager.create_thread()
        thread_id = thread.thread_id
    
    # Check if a task is already running for this thread
    if thread_id in active_sessions and active_sessions[thread_id].get("status") == "running":
        # Return existing session info - client should subscribe to stream
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'init', 'thread_id': thread_id, 'status': 'already_running'})}\n\n"]),
            media_type="text/event-stream"
        )
    
    # Update thread title based on first user message
    thread = thread_manager.get_thread(thread_id)
    if thread and thread.title == "New Chat":
        title = request.prompt[:50] + ("..." if len(request.prompt) > 50 else "")
        thread_manager.update_thread_title(thread_id, title)
    
    thread_manager.update_thread_timestamp(thread_id)
    
    # Configure agent with thread_id for persistent state
    config = {"configurable": {"thread_id": thread_id}}
    if request.parent_checkpoint_id:
        config["configurable"]["checkpoint_id"] = request.parent_checkpoint_id

    # Initialize session tracking
    active_sessions[thread_id] = {
        "status": "running",
        "events": [],
        "last_content": "",
        "prompt": request.prompt,
        "deep_research": request.deep_research,
        "started_at": datetime.now().isoformat()
    }
    
    # Create message queue for this session
    message_queues[thread_id] = asyncio.Queue(maxsize=1000)
    
    # START DETACHED BACKGROUND TASK - This is the key fix!
    # The task runs independently of the HTTP connection
    task = asyncio.create_task(
        run_agent_background(agent, thread_id, request.prompt, config, request.deep_research)
    )
    background_tasks[thread_id] = task
    
    # Return SSE stream that reads from the queue
    async def event_generator():
        """Stream events from the background task to the client"""
        try:
            queue = message_queues.get(thread_id)
            if not queue:
                yield f"data: {json.dumps({'type': 'error', 'error': 'Queue not found'})}\n\n"
                return
            
            # Stream events until done or error
            while True:
                try:
                    # Wait for next event with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    # Stop if we got a terminal event
                    if event.get('type') in ('done', 'error'):
                        break
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                    
                    # Check if session is still running
                    if thread_id in active_sessions:
                        status = active_sessions[thread_id].get("status")
                        if status in ("completed", "error", "cancelled"):
                            break
                    else:
                        break
        except asyncio.CancelledError:
            # Client disconnected - that's OK, background task continues!
            print(f"📡 Client disconnected from stream for thread {thread_id} - background task continues")
            pass
    
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
            if isinstance(content, str) and ("[DOWNLOAD_DOCX]" in content or "[DOWNLOAD_PDF]" in content):
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
            
            content = content.strip()

        # Ensure tool_calls and name are included for UI status display
        return {
            "type": data.get("type"),
            "content": content,
            "tool_calls": data.get("tool_calls", []),
            "name": data.get("name"),
            "role": data.get("role")
        }
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
            
            if key == "messages":
                # Direct messages list - check if iterable
                if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                    for msg in value:
                        serialized = _serialize_message(msg)
                        if serialized:
                            messages.append(serialized)
                elif hasattr(value, 'content'):
                    # Single message object
                    serialized = _serialize_message(value)
                    if serialized:
                        messages.append(serialized)
            elif isinstance(value, dict) and "messages" in value:
                # Node output with messages (e.g., {'agent': {'messages': [...]}})
                msg_list = value["messages"]
                if hasattr(msg_list, '__iter__') and not isinstance(msg_list, (str, bytes)):
                    for msg in msg_list:
                        serialized = _serialize_message(msg)
                        if serialized:
                            messages.append(serialized)
            elif isinstance(value, list):
                # List of messages directly
                for item in value:
                    if hasattr(item, "content") or (isinstance(item, dict) and "content" in item):
                        serialized = _serialize_message(item)
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
# Local Run
# -----------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
