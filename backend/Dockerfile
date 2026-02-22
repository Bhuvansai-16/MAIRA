# Backend Dockerfile for MAIRA
# Based on python:3.11-slim. Installs system deps needed by common Python packages

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# Install system dependencies required by some packages (psycopg, lxml, pillow, etc.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
        libxml2-dev \
        libxslt1-dev \
        libjpeg-dev \
        zlib1g-dev \
        libffi-dev \
        poppler-utils \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt ./requirements.txt

# Install Python dependencies
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Expose the port the app runs on
EXPOSE 8000

# Recommended environment variables to set at deploy time:
# SUPABASE_URL, MAIRA_PASSWORD, SUPABASE_JWT_SECRET, GEMINI_API_KEY, etc.

# Use Uvicorn for running FastAPI. In Cloud Run you can set concurrency and adjust workers.
# Use --proxy-headers to respect X-Forwarded-* headers from GCP load balancers.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]
