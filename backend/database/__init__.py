"""
Database module for MAIRA Agent

This module handles PostgreSQL (Supabase) connections for:
- Chat history and checkpoints (short-term)
- Long-term memory store (persistent across threads)
- User and thread management
"""

from .postgres import (
    pool, 
    _checkpointer_pool,
    get_checkpointer, 
    get_store, 
    DB_URI, 
    open_all_pools,
    reset_pool,
    validate_pool,
    ensure_healthy_pool,
    _is_transient_error,
    # User management
    get_user_by_id,
    user_exists,
    sync_user,
    # Thread management
    get_threads_by_user,
    create_thread_for_user,
    get_thread_by_id,
    update_thread_title,
    delete_thread,
)

# Vector store (PGVector + Google Generative AI Embeddings)
from .vector_store import (
    vector_store,
    search_knowledge_base,
    ingest_pdf,
    ingest_text,
    ingest_image_description,
    delete_user_documents,
    embeddings as google_embeddings,
)

__all__ = [
    'pool',
    '_checkpointer_pool',
    'get_checkpointer',
    'get_store',
    'DB_URI',
    'open_all_pools',
    'reset_pool',
    'validate_pool',
    'ensure_healthy_pool',
    '_is_transient_error',
    # User management
    'get_user_by_id',
    'user_exists',
    'sync_user',
    # Thread management
    'get_threads_by_user',
    'create_thread_for_user',
    'get_thread_by_id',
    'update_thread_title',
    'delete_thread',
    # Vector store
    'vector_store',
    'search_knowledge_base',
    'ingest_pdf',
    'ingest_text',
    'ingest_image_description',
    'delete_user_documents',
    'google_embeddings',
]
