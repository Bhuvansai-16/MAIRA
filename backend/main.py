from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from main_agent import agent 
from thread_manager import thread_manager, Thread
import json

app = FastAPI(title="MAIRA – Deep Research Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# -----------------------------
# Request Schemas
# -----------------------------

class AgentRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = None  # If not provided, creates new thread
    deep_research: bool = False  # When True, enables full Tier 3 research workflow


class CreateThreadRequest(BaseModel):
    title: Optional[str] = None


class UpdateThreadRequest(BaseModel):
    title: str


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
async def get_thread_messages(thread_id: str):
    """Get all messages for a specific thread"""
    if not thread_manager.thread_exists(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    
    try:
        # Get state from checkpointer using thread_id config
        config = {"configurable": {"thread_id": thread_id}}
        state = agent.get_state(config)
        
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
# Agent Endpoint
# -----------------------------

@app.post("/run-agent")
async def run_agent(request: AgentRequest):
    """Run the agent with thread-based conversation tracking using SSE streaming"""
    if not request.prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    # Get or create thread
    thread_id = request.thread_id
    if not thread_id:
        # Create new thread
        thread = thread_manager.create_thread()
        thread_id = thread.thread_id
    elif not thread_manager.thread_exists(thread_id):
        # Create thread with the provided ID
        thread = thread_manager.create_thread()
        thread_id = thread.thread_id
    
    # Update thread title based on first user message
    thread = thread_manager.get_thread(thread_id)
    if thread and thread.title == "New Chat":
        # Generate title from first message (first 50 chars)
        title = request.prompt[:50] + ("..." if len(request.prompt) > 50 else "")
        thread_manager.update_thread_title(thread_id, title)
    
    # Update thread timestamp
    thread_manager.update_thread_timestamp(thread_id)
    
    # Configure agent with thread_id for persistent state
    config = {"configurable": {"thread_id": thread_id}}

    async def event_generator():
        """Generate SSE events from agent stream"""
        try:
            # Send thread_id as the first event
            yield f"data: {json.dumps({'thread_id': thread_id, 'type': 'init'})}\n\n"
            
            # Stream agent updates
            # Prefix message with mode indicator for agent routing
            mode_prefix = "[MODE: DEEP_RESEARCH] " if request.deep_research else "[MODE: CHAT] "
            user_content = mode_prefix + request.prompt
            
            async for chunk in agent.astream(
                {"messages": [{"role": "user", "content": user_content}]},
                config=config,
                stream_mode="updates"
            ):
                serialized = _serialize_chunk(chunk)
                if serialized:
                    yield f"data: {json.dumps(serialized)}\n\n"
            
            # Send completion event
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

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
            
            # Strip generic default greetings that get prepended
            content = content.replace("Hello! How can I help you today?", "")
            
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
            if key == "messages":
                # Direct messages list
                for msg in value:
                    serialized = _serialize_message(msg)
                    if serialized:
                        messages.append(serialized)
            elif isinstance(value, dict) and "messages" in value:
                # Node output with messages (e.g., {'agent': {'messages': [...]}})
                for msg in value["messages"]:
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
