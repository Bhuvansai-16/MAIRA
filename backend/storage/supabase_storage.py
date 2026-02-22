"""
Supabase Storage Client for MAIRA Agent

Provides storage functionality for:
- Export files: Generated PDFs and DOCXs from report generation

Storage Buckets:
- research-exports: Store generated PDFs/DOCXs for download
"""

import os
import base64
from typing import Optional, Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv

# Try to import supabase-py
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ supabase-py not installed. Run: pip install supabase")

load_dotenv()

# =====================================================
# CONFIGURATION
# =====================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://pteanoqxjpdumsazcalr.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Bucket names
BUCKETS = {
    "exports": "research-exports",  # Generated PDF/DOCX files
}

# =====================================================
# CUSTOM EXCEPTIONS
# =====================================================

class StorageError(Exception):
    """Custom exception for storage operations."""
    pass

# =====================================================
# SUPABASE CLIENT SINGLETON
# =====================================================

_supabase_client: Optional["Client"] = None

def get_supabase_client() -> Optional["Client"]:
    """Get or create the Supabase client singleton."""
    global _supabase_client
    
    if not SUPABASE_AVAILABLE:
        return None
    
    if _supabase_client is None:
        # Use service key if available (for server-side operations), otherwise anon key
        key = SUPABASE_SERVICE_KEY if SUPABASE_SERVICE_KEY else SUPABASE_ANON_KEY
        if SUPABASE_URL and key:
            try:
                _supabase_client = create_client(SUPABASE_URL, key)
                print(f"✅ Supabase storage client initialized")
            except Exception as e:
                print(f"⚠️ Failed to initialize Supabase client: {e}")
                return None
    
    return _supabase_client


# Singleton storage instance
class SupabaseStorage:
    """Wrapper class for Supabase storage operations."""
    
    def __init__(self):
        self.client = get_supabase_client()
        self._buckets_verified = False
    
    @property
    def is_available(self) -> bool:
        """Check if Supabase storage is available."""
        return self.client is not None
    
    def ensure_buckets_exist(self):
        """Verify required buckets exist (assumes they were created in Supabase dashboard)."""
        if not self.is_available or self._buckets_verified:
            return
        
        try:
            for bucket_name in BUCKETS.values():
                try:
                    # Try to list files in bucket - if it works, bucket exists
                    self.client.storage.from_(bucket_name).list()
                    print(f"  ✓ Bucket '{bucket_name}' verified")
                except Exception as e:
                    # Bucket doesn't exist or no access - log warning but continue
                    print(f"  ⚠️ Bucket '{bucket_name}' not accessible: {e}")
                    print(f"     Please create it manually in Supabase Dashboard → Storage")
            
            self._buckets_verified = True
        except Exception as e:
            print(f"⚠️ Error verifying buckets: {e}")
    
    def upload_file(
        self,
        bucket: str,
        path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        upsert: bool = True
    ) -> Dict[str, Any]:
        """
        Upload a file to Supabase storage.
        
        Args:
            bucket: Bucket name
            path: File path within bucket
            data: File content as bytes
            content_type: MIME type
            upsert: If True, overwrite existing file
        
        Returns:
            Dict with upload result including path and URL
        """
        if not self.is_available:
            raise StorageError("Supabase storage is not available")
        
        self.ensure_buckets_exist()
        
        try:
            # Upload the file
            result = self.client.storage.from_(bucket).upload(
                path=path,
                file=data,
                file_options={
                    "content-type": content_type,
                    "upsert": str(upsert).lower()
                }
            )
            
            # Get public URL
            public_url = self.client.storage.from_(bucket).get_public_url(path)
            
            return {
                "success": True,
                "path": path,
                "bucket": bucket,
                "url": public_url,
                "size": len(data),
            }
        except Exception as e:
            error_msg = str(e)
            # Handle duplicate key error by trying upsert
            if "Duplicate" in error_msg and not upsert:
                return self.upload_file(bucket, path, data, content_type, upsert=True)
            raise StorageError(f"Failed to upload file: {e}")
    
    def download_file(self, bucket: str, path: str) -> bytes:
        """Download a file from Supabase storage."""
        if not self.is_available:
            raise StorageError("Supabase storage is not available")
        
        try:
            response = self.client.storage.from_(bucket).download(path)
            return response
        except Exception as e:
            raise StorageError(f"Failed to download file: {e}")
    
    def get_public_url(self, bucket: str, path: str) -> str:
        """Get the public URL for a file."""
        if not self.is_available:
            raise StorageError("Supabase storage is not available")
        
        return self.client.storage.from_(bucket).get_public_url(path)
    
    def delete_file(self, bucket: str, path: str) -> bool:
        """Delete a file from storage."""
        if not self.is_available:
            raise StorageError("Supabase storage is not available")
        
        try:
            self.client.storage.from_(bucket).remove([path])
            return True
        except Exception as e:
            print(f"⚠️ Failed to delete file: {e}")
            return False
    
    def list_files(self, bucket: str, folder: str = "") -> List[Dict[str, Any]]:
        """List files in a bucket/folder."""
        if not self.is_available:
            raise StorageError("Supabase storage is not available")
        
        try:
            result = self.client.storage.from_(bucket).list(folder)
            return result
        except Exception as e:
            raise StorageError(f"Failed to list files: {e}")


# Global storage instance
supabase_storage = SupabaseStorage()


# =====================================================
# HIGH-LEVEL HELPER FUNCTIONS
# =====================================================

def upload_export_file(
    file_data: bytes | str,
    filename: str,
    thread_id: str,
    user_id: str = None,
    file_type: str = "pdf",
) -> Dict[str, Any]:
    """
    Upload a generated export file (PDF/DOCX) to storage for download.
    
    Args:
        file_data: File bytes or base64 string
        filename: The filename (with or without extension)
        thread_id: The thread ID this export belongs to
        user_id: Optional user ID for organization
        file_type: "pdf" or "docx"
    
    Returns:
        Dict with file info including download URL
    """
    # Handle base64 input
    if isinstance(file_data, str):
        file_bytes = base64.b64decode(file_data)
    else:
        file_bytes = file_data
    
    # Determine content type
    content_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    content_type = content_types.get(file_type, "application/octet-stream")
    
    # Ensure proper extension
    ext = f".{file_type}"
    if not filename.lower().endswith(ext):
        filename = f"{filename}{ext}"
    
    # Clean filename
    clean_filename = filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
    
    # Create storage path: exports/thread_id/filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    path = f"{thread_id}/{timestamp}_{clean_filename}"
    
    # Upload to storage
    result = supabase_storage.upload_file(
        bucket=BUCKETS["exports"],
        path=path,
        data=file_bytes,
        content_type=content_type
    )
    
    # Add metadata
    result["filename"] = clean_filename
    result["original_filename"] = filename
    result["thread_id"] = thread_id
    result["user_id"] = user_id
    result["file_type"] = file_type
    result["size_kb"] = len(file_bytes) / 1024
    
    print(f"  📄 Uploaded export: {clean_filename} ({result['size_kb']:.1f}KB)")
    
    return result


def get_file_public_url(bucket_key: str, path: str) -> str:
    """
    Get the public URL for a file.
    
    Args:
        bucket_key: Key from BUCKETS dict ("exports")
        path: File path within bucket
    
    Returns:
        Public URL string
    """
    bucket = BUCKETS.get(bucket_key, bucket_key)
    return supabase_storage.get_public_url(bucket, path)


def delete_file(bucket_key: str, path: str) -> bool:
    """Delete a file from storage."""
    bucket = BUCKETS.get(bucket_key, bucket_key)
    return supabase_storage.delete_file(bucket, path)


def list_export_files(thread_id: str) -> List[Dict[str, Any]]:
    """
    List all export files (PDF/DOCX) for a thread.
    
    Args:
        thread_id: The thread ID
    
    Returns:
        List of file info dicts with URLs
    """
    try:
        files = supabase_storage.list_files(BUCKETS["exports"], thread_id)
        
        results = []
        for f in files:
            name = f.get("name", "")
            if not name:
                continue
            
            path = f"{thread_id}/{name}"
            
            # Determine file type from extension
            file_type = "pdf" if name.lower().endswith(".pdf") else "docx"
            
            results.append({
                "filename": name,
                "path": path,
                "url": supabase_storage.get_public_url(BUCKETS["exports"], path),
                "file_type": file_type,
                "size": f.get("metadata", {}).get("size", 0),
                "created": f.get("created_at"),
            })
        
        return results
    except StorageError:
        return []


# =====================================================
# INITIALIZATION
# =====================================================

def init_storage():
    """Initialize storage and ensure buckets exist."""
    if supabase_storage.is_available:
        supabase_storage.ensure_buckets_exist()
        return True
    else:
        print("⚠️ Supabase storage not available - files will not be persisted")
        return False


# Auto-initialize on import
if SUPABASE_AVAILABLE:
    try:
        init_storage()
    except Exception as e:
        print(f"⚠️ Storage initialization error: {e}")
