"""
Security Module for MAIRA Backend

Provides:
- JWT token verification (Supabase Auth compatible)
- Authentication dependency for FastAPI endpoints
- Input sanitization utilities
- File upload size limits

IMPORTANT: Authentication can be disabled for local development by setting
    AUTH_DISABLED=true
in your .env file. In production, NEVER set this.
"""

import os
import re
import hmac
import hashlib
import base64
import json
from typing import Optional
from datetime import datetime, timezone

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

# =====================================================
# CONFIGURATION
# =====================================================

# Set AUTH_DISABLED=true in .env for local development without auth
AUTH_DISABLED = os.getenv("AUTH_DISABLED", "false").lower() in ("true", "1", "yes")

# Supabase JWT secret (used to verify tokens)
# This is the JWT secret from your Supabase project settings > API > JWT Secret
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# Maximum file upload sizes (in bytes)
MAX_DOCUMENT_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024  # Default: 50MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB for images

# Maximum prompt length (characters)
MAX_PROMPT_LENGTH = 50_000

# CORS allowed origins (comma-separated list)
# Default allows common local dev ports
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://localhost:8080"
    ).split(",")
    if origin.strip()
]

# =====================================================
# JWT VERIFICATION (Supabase-compatible)
# =====================================================

_bearer_scheme = HTTPBearer(auto_error=False)


def _base64url_decode(data: str) -> bytes:
    """Decode base64url-encoded data (JWT uses this variant)."""
    # Add padding if needed
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def verify_jwt(token: str) -> dict:
    """
    Verify a Supabase JWT token using HMAC-SHA256.
    
    Returns the decoded payload if valid.
    Raises HTTPException if invalid.
    """
    if not SUPABASE_JWT_SECRET:
        # If no JWT secret is configured, we can't verify tokens
        # In production this should be a hard error
        raise HTTPException(
            status_code=500,
            detail="JWT secret not configured. Set SUPABASE_JWT_SECRET in .env"
        )
    
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid token format")
        
        header_b64, payload_b64, signature_b64 = parts
        
        # Verify signature using HMAC-SHA256
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        secret_bytes = SUPABASE_JWT_SECRET.encode("utf-8")
        expected_signature = hmac.new(
            secret_bytes, signing_input, hashlib.sha256
        ).digest()
        actual_signature = _base64url_decode(signature_b64)
        
        if not hmac.compare_digest(expected_signature, actual_signature):
            raise HTTPException(status_code=401, detail="Invalid token signature")
        
        # Decode payload
        payload = json.loads(_base64url_decode(payload_b64))
        
        # Check expiration
        exp = payload.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            raise HTTPException(status_code=401, detail="Token expired")
        
        return payload
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[dict]:
    """
    FastAPI dependency to extract and verify the current user from JWT.
    
    Usage:
        @app.get("/protected")
        def protected_route(user: dict = Depends(get_current_user)):
            user_id = user["sub"]
            ...
    
    When AUTH_DISABLED=true (local dev), returns a mock user.
    """
    if AUTH_DISABLED:
        # Local development mode — skip auth, return mock user
        return {
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "dev@local",
            "role": "authenticated",
            "auth_disabled": True,
        }
    
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = verify_jwt(credentials.credentials)
    return payload


async def optional_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[dict]:
    """
    Like get_current_user but doesn't fail if no token is provided.
    Returns None for unauthenticated requests.
    Useful for endpoints that work with or without auth.
    """
    if AUTH_DISABLED:
        return {
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "dev@local",
            "role": "authenticated",
            "auth_disabled": True,
        }
    
    if not credentials:
        return None
    
    try:
        return verify_jwt(credentials.credentials)
    except HTTPException:
        return None


# =====================================================
# INPUT SANITIZATION
# =====================================================

def sanitize_prompt(prompt: str) -> str:
    """
    Sanitize user prompt input:
    - Strip control characters (except newlines/tabs)
    - Enforce maximum length
    - Strip leading/trailing whitespace
    
    Does NOT modify any [MODE:...] or [PERSONA:...] tags
    as those are added server-side by main.py.
    """
    if not prompt:
        return prompt
    
    # Enforce max length
    if len(prompt) > MAX_PROMPT_LENGTH:
        prompt = prompt[:MAX_PROMPT_LENGTH]
    
    # Remove control characters except \n, \r, \t
    prompt = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', prompt)
    
    return prompt.strip()


def validate_file_size(content_length: int, max_size: int, file_type: str = "file"):
    """
    Validate file upload size.
    Raises HTTPException(413) if too large.
    """
    if content_length > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = content_length / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"{file_type.capitalize()} too large: {actual_mb:.1f}MB. Maximum is {max_mb:.0f}MB."
        )


# =====================================================
# STARTUP BANNER
# =====================================================

if AUTH_DISABLED:
    print("⚠️  AUTH_DISABLED=true — Authentication is OFF (local dev mode)")
else:
    if SUPABASE_JWT_SECRET:
        print("🔒 Security module loaded — JWT authentication enabled")
    else:
        print("⚠️  SUPABASE_JWT_SECRET not set — JWT verification will fail at runtime")

print(f"📏 Upload limits: Documents={MAX_DOCUMENT_SIZE // (1024*1024)}MB, Images={MAX_IMAGE_SIZE // (1024*1024)}MB")
print(f"🌐 CORS origins: {ALLOWED_ORIGINS}")
