"""
Thread Manager - UUID v7 based thread management for conversation history
With SqliteSaver for persistent checkpoints and state history support.
"""
import uuid
import time
import os
import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

# Database path for persistent storage
DB_DIR = os.path.join(os.path.dirname(__file__), 'data')
DB_PATH = os.path.join(DB_DIR, 'maira_threads.db')

# Ensure data directory exists
os.makedirs(DB_DIR, exist_ok=True)


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
    Stores thread metadata in memory (can be extended to use database).
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
        """Get a thread by ID"""
        return self._threads.get(thread_id)
    
    def thread_exists(self, thread_id: str) -> bool:
        """Check if a thread exists"""
        return thread_id in self._threads
    
    def get_all_threads(self) -> List[Thread]:
        """Get all threads, sorted by creation time (newest first)"""
        threads = list(self._threads.values())
        # UUID v7 is naturally sortable by time, so we can sort by thread_id
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
        """Delete a thread"""
        if thread_id in self._threads:
            del self._threads[thread_id]
            return True
        return False
    
    def save_to_db(self):
        """Persist threads to SQLite database"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS threads (
                thread_id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT,
                updated_at TEXT,
                parent_thread_id TEXT,
                fork_checkpoint_id TEXT
            )
        ''')
        for thread in self._threads.values():
            cursor.execute('''
                INSERT OR REPLACE INTO threads 
                (thread_id, title, created_at, updated_at, parent_thread_id, fork_checkpoint_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                thread.thread_id, 
                thread.title, 
                thread.created_at, 
                thread.updated_at,
                getattr(thread, 'parent_thread_id', None),
                getattr(thread, 'fork_checkpoint_id', None)
            ))
        conn.commit()
        conn.close()
    
    def load_from_db(self):
        """Load threads from SQLite database"""
        if not os.path.exists(DB_PATH):
            return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="threads"')
        if not cursor.fetchone():
            conn.close()
            return
        cursor.execute('SELECT thread_id, title, created_at, updated_at FROM threads')
        for row in cursor.fetchall():
            thread = Thread(
                thread_id=row[0],
                title=row[1],
                created_at=row[2],
                updated_at=row[3]
            )
            self._threads[thread.thread_id] = thread
        conn.close()
    
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
        # Store branch metadata
        thread.parent_thread_id = parent_thread_id  # type: ignore
        thread.fork_checkpoint_id = fork_checkpoint_id  # type: ignore
        self._threads[thread_id] = thread
        self.save_to_db()
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
    
    def thread_exists(self, thread_id: str) -> bool:
        """Check if a thread exists"""
        return thread_id in self._threads


# Global thread manager instance
thread_manager = ThreadManager()
