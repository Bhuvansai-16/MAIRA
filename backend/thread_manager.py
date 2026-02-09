"""
Thread Manager - UUID v7 based thread management for conversation history
Uses PostgreSQL (Supabase) for persistent storage via LangGraph checkpoints.
"""
import uuid
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict


def generate_uuid_v7() -> str:
    """
    Generate a UUID v7 (time-ordered UUID).
    UUID v7 uses Unix timestamp in milliseconds for the first 48 bits,
    making it sortable by creation time.
    """
    # Get current timestamp in milliseconds
    timestamp_ms = int(time.time() * 1000)
    
    # Generate random bits for the rest
    random_bits = uuid.uuid4().int & ((1 << 74) - 1)  # 74 random bits
    
    # Construct UUID v7
    # First 48 bits: timestamp
    # Next 4 bits: version (7)
    # Next 12 bits: random
    # Next 2 bits: variant (10)
    # Last 62 bits: random
    
    uuid_int = (timestamp_ms << 80) | (0x7 << 76) | (random_bits & ((1 << 76) - 1))
    uuid_int = (uuid_int & ~(0x3 << 62)) | (0x2 << 62)  # Set variant bits
    
    # Format as UUID string
    hex_str = f'{uuid_int:032x}'
    return f'{hex_str[:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:]}'


@dataclass
class Thread:
    """Represents a conversation thread"""
    thread_id: str
    title: str = "New Chat"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ThreadManager:
    """
    Manages conversation threads with UUID v7 identifiers.
    In-memory cache only - persistence handled by PostgreSQL checkpoints.
    Thread metadata is reconstructed from checkpoint data on demand.
    """
    
    def __init__(self):
        self._threads: Dict[str, Thread] = {}
    
    def create_thread(self, title: Optional[str] = None) -> Thread:
        """Create a new thread with UUID v7 identifier"""
        thread_id = generate_uuid_v7()
        thread = Thread(
            thread_id=thread_id,
            title=title or "New Chat"
        )
        self._threads[thread_id] = thread
        return thread
    
    def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID from in-memory cache"""
        return self._threads.get(thread_id)
    
    def thread_exists(self, thread_id: str) -> bool:
        """Check if a thread exists in memory"""
        return thread_id in self._threads
    
    def get_all_threads(self) -> List[Thread]:
        """Get all threads, sorted by creation time (newest first)"""
        threads = list(self._threads.values())
        # UUID v7 is naturally sortable by time
        threads.sort(key=lambda t: t.thread_id, reverse=True)
        return threads
    
    def update_thread_title(self, thread_id: str, title: str) -> Optional[Thread]:
        """Update the title of a thread"""
        thread = self._threads.get(thread_id)
        if thread:
            thread.title = title
            thread.updated_at = datetime.now().isoformat()
        return thread
    
    def update_thread_timestamp(self, thread_id: str) -> Optional[Thread]:
        """Update the last activity timestamp"""
        thread = self._threads.get(thread_id)
        if thread:
            thread.updated_at = datetime.now().isoformat()
        return thread
    
    def delete_thread(self, thread_id: str) -> bool:
        """
        Delete a thread from in-memory cache.
        PostgreSQL deletion is handled separately in the API endpoint.
        """
        if thread_id in self._threads:
            del self._threads[thread_id]
            return True
        return False
    
    def create_branch(self, parent_thread_id: str, fork_checkpoint_id: str, title: Optional[str] = None) -> Optional[Thread]:
        """Create a new branch from an existing thread at a specific checkpoint"""
        parent = self.get_thread(parent_thread_id)
        if not parent:
            return None
        
        thread_id = generate_uuid_v7()
        thread = Thread(
            thread_id=thread_id,
            title=title or f"Branch of {parent.title}"
        )
        # Store branch metadata as dynamic attributes
        thread.parent_thread_id = parent_thread_id  # type: ignore
        thread.fork_checkpoint_id = fork_checkpoint_id  # type: ignore
        self._threads[thread_id] = thread
        return thread


@dataclass
class CheckpointInfo:
    """Represents checkpoint metadata for time travel"""
    checkpoint_id: str
    thread_id: str
    timestamp: str
    message_count: int
    parent_checkpoint_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Global thread manager instance
thread_manager = ThreadManager()
