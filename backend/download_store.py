"""
Download Store – dual-layer persistence for generated reports.

Layer 1 (primary):   In-memory global per tool (pdftool / doctool / latextoformate).
Layer 2 (fallback):  Supabase Storage bucket "research-exports".

Write-path (called from _store_pending_download in each tool):
    save_to_supabase(thread_id, filename, base64_data)
    → Uploads the file to  research-exports/<thread_id>/<timestamp>_<filename>

Read-path (called from main.py when in-memory is empty after SSL crash):
    get_downloads_from_supabase(thread_id)
    → Lists + downloads the most recent file(s) for that thread,
      returning [{filename, data (base64), url}]
"""

import threading
import base64
from typing import Optional, Dict, Any, List

_upload_lock = threading.Lock()


# -------------------------------------------------------
# SUPABASE HELPERS (lazy-import to avoid circular deps)
# -------------------------------------------------------

def _get_storage():
    """Lazy-import the storage module."""
    try:
        from storage.supabase_storage import supabase_storage, BUCKETS
        if supabase_storage.is_available:
            return supabase_storage, BUCKETS
    except Exception as e:
        print(f"  ⚠️ Supabase storage not available: {e}")
    return None, None


def save_to_supabase(thread_id: str, filename: str, base64_data: str) -> Optional[str]:
    """
    Upload a generated file to Supabase Storage.
    Returns the public URL on success, None on failure.
    Non-blocking: failures are logged but never raise.
    """
    storage, buckets = _get_storage()
    if storage is None:
        return None

    try:
        from datetime import datetime
        # Decode base64 → raw bytes
        file_bytes = base64.b64decode(base64_data)

        # Determine content type
        lower_fn = filename.lower()
        if lower_fn.endswith(".pdf"):
            ct = "application/pdf"
        elif lower_fn.endswith(".docx"):
            ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            ct = "application/octet-stream"

        # Clean filename & build path
        clean = filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"{thread_id}/{ts}_{clean}"

        with _upload_lock:
            result = storage.upload_file(
                bucket=buckets["exports"],
                path=path,
                data=file_bytes,
                content_type=ct,
            )
        url = result.get("url", "")
        print(f"  ☁️  Uploaded to Supabase: {clean} ({len(file_bytes)/1024:.1f}KB) → {url[:80]}")
        return url

    except Exception as e:
        print(f"  ⚠️ Supabase upload failed (non-fatal): {e}")
        return None


def get_downloads_from_supabase(thread_id: str) -> List[Dict[str, Any]]:
    """
    Fetch all stored downloads for a thread from Supabase Storage.
    Returns list of dicts:  [{filename, data (base64 str), url, file_type}]
    """
    storage, buckets = _get_storage()
    if storage is None:
        return []

    try:
        files = storage.list_files(buckets["exports"], thread_id)
        # Sort files by name in reverse order (latest timestamp first)
        files.sort(key=lambda x: x.get("name", ""), reverse=True)
        results = []
        for f in files:
            name = f.get("name", "")
            if not name:
                continue
            path = f"{thread_id}/{name}"
            try:
                raw_bytes = storage.download_file(buckets["exports"], path)
                b64 = base64.b64encode(raw_bytes).decode("utf-8")
                # Strip timestamp prefix from display name
                display = name.split("_", 2)[-1] if name.count("_") >= 2 else name
                file_type = "pdf" if name.lower().endswith(".pdf") else "docx"
                results.append({
                    "filename": display,
                    "data": b64,
                    "file_type": file_type,
                    "url": storage.get_public_url(buckets["exports"], path),
                })
            except Exception as dl_err:
                print(f"  ⚠️ Failed to download {name}: {dl_err}")

        return results

    except Exception as e:
        print(f"  ⚠️ Supabase list failed: {e}")
        return []
