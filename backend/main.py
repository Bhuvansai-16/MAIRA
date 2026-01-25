from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from main_agent import agent 
from thread_manager import thread_manager, Thread

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
    """Run the agent with thread-based conversation tracking"""
    if not request.prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    try:
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
        
        result = agent.invoke(
            {
                "messages": [
                    {"role": "user", "content": request.prompt}
                ]
            },
            config=config
        )

        # Prepare messages for JSON serialization
        messages_output = []
        for msg in result["messages"]:
            msg_data = _serialize_message(msg)
            if msg_data:
                messages_output.append(msg_data)

        return {
            "output": messages_output,
            "thread_id": thread_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed: {str(e)}"
        )


def _serialize_message(msg) -> Optional[Dict[str, Any]]:
    """Helper function to serialize a message to dict"""
    try:
        if hasattr(msg, "model_dump"):
            return msg.model_dump()
        elif hasattr(msg, "dict"):
            return msg.dict()
        elif hasattr(msg, "content"):
            return {
                "content": msg.content,
                "type": getattr(msg, "type", "ai"),
                "role": getattr(msg, "role", "assistant")
            }
        elif isinstance(msg, dict):
            return msg
        else:
            return {"content": str(msg), "type": "unknown"}
    except Exception:
        return None


# -----------------------------
# Local Run
# -----------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
