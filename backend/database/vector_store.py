"""
PGVector Store for MAIRA Agent

Handles:
- Document embedding & storage using Google Generative AI embeddings
- Similarity search for RAG (Retrieval-Augmented Generation)
- Document ingestion from PDFs, text files, and images
- User-scoped document retrieval

Uses the same Supabase PostgreSQL database with pgvector extension.
"""

import os
from dotenv import load_dotenv
from langchain_postgres import PGVector
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.runnables import RunnableConfig
from langchain.tools import tool

load_dotenv()

# =====================================================
# SUPABASE CONNECTION (reuse from postgres.py)
# =====================================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_PROJECT_REF = (
    SUPABASE_URL.replace("https://", "").replace(".supabase.co", "")
    if SUPABASE_URL
    else ""
)
SUPABASE_PASSWORD = os.getenv("MAIRA_PASSWORD", "")

# Connection string for PGVector (uses psycopg3 driver)
# Fix #15: add SSL + TCP keepalive params to prevent stale connections
VECTOR_DB_URI = (
    f"postgresql+psycopg://postgres:{SUPABASE_PASSWORD}"
    f"@db.{SUPABASE_PROJECT_REF}.supabase.co:5432/postgres"
    f"?sslmode=require&connect_timeout=10&keepalives=1"
    f"&keepalives_idle=10&keepalives_interval=3&keepalives_count=5"
)

# =====================================================
# EMBEDDINGS (Google Generative AI)
# =====================================================
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

# =====================================================
# PGVECTOR STORE INSTANCE
# =====================================================
COLLECTION_NAME = "user_documents"

vector_store = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=VECTOR_DB_URI,
    use_jsonb=True,
)

print(f"✅ PGVector store initialized (collection: {COLLECTION_NAME})")

# Fix #7: Module-level shared SQLAlchemy engine for direct SQL operations.
# Reusing a single engine (with its own pool) avoids per-call engine creation.
from sqlalchemy import create_engine as _create_engine
_sql_engine = _create_engine(VECTOR_DB_URI, pool_size=2, max_overflow=1)

# =====================================================
# TEXT SPLITTER (for chunking documents)
# =====================================================
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


# =====================================================
# RETRIEVAL TOOL (for the Deep Agent)
# =====================================================
@tool
def search_knowledge_base(query: str, config: RunnableConfig) -> str:
    """Search the user's uploaded documents for relevant information.

    Use this when:
    - The user refers to 'my files', 'the upload', 'this document', or 'my paper'
    - The user asks questions about specific content they previously uploaded
    - You need context from the user's personal knowledge base
    - The user uploaded a document and asks you to read, analyze, or summarize it

    Args:
        query: The search query to find relevant document chunks.

    Returns:
        Concatenated relevant document excerpts with source metadata.
    """
    # Extract user_id from the thread configuration for multi-tenant isolation
    user_id = config.get("configurable", {}).get("user_id")

    if not user_id:
        return "Error: No user_id found in configuration. Cannot search personal knowledge base."

    try:
        docs = vector_store.similarity_search(
            query,
            k=5,
            filter={"user_id": user_id},
        )
        if not docs:
            return "No relevant documents found in the knowledge base. The user may not have uploaded any files yet."

        results = []
        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "")
            page_info = f" (Page {page + 1})" if page != "" else ""

            results.append(
                f"--- Document {i}{page_info} ---\n"
                f"Source: {source}\n"
                f"{doc.page_content}\n"
            )

        return "\n\n".join(results)
    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"


# =====================================================
# INGESTION FUNCTIONS
# =====================================================
def ingest_pdf(file_path: str, user_id: str, metadata: dict = None) -> int:
    """
    Ingest a PDF file into the vector store.

    Args:
        file_path: Path to the PDF file.
        user_id: The user who uploaded the file.
        metadata: Optional extra metadata to attach.

    Returns:
        Number of chunks ingested.
    """
    loader = PyPDFLoader(file_path)
    pages = loader.load()

    # Split into chunks
    chunks = text_splitter.split_documents(pages)

    # Attach user metadata
    for chunk in chunks:
        chunk.metadata["user_id"] = user_id
        chunk.metadata["file_type"] = "pdf"
        if metadata:
            chunk.metadata.update(metadata)

    vector_store.add_documents(chunks)
    print(f"✅ Ingested {len(chunks)} chunks from PDF: {file_path}")
    return len(chunks)


def ingest_text(text: str, user_id: str, source: str = "direct_input", metadata: dict = None) -> int:
    """
    Ingest raw text into the vector store.

    Args:
        text: The text content to ingest.
        user_id: The user who uploaded the text.
        source: A label for the source (e.g., filename).
        metadata: Optional extra metadata.

    Returns:
        Number of chunks ingested.
    """
    # Split into chunks
    chunks = text_splitter.create_documents(
        texts=[text],
        metadatas=[{
            "source": source,
            "user_id": user_id,
            "file_type": "text",
            **(metadata or {}),
        }],
    )

    vector_store.add_documents(chunks)
    print(f"✅ Ingested {len(chunks)} chunks from text: {source}")
    return len(chunks)


def ingest_image_description(
    description: str, user_id: str, image_filename: str, metadata: dict = None
) -> int:
    """
    Ingest an image by storing its text description as a document.
    The caller should use a multimodal model (e.g., Gemini) to generate
    the description before calling this function.

    Args:
        description: Text description of the image content.
        user_id: The user who uploaded the image.
        image_filename: Original filename of the image.
        metadata: Optional extra metadata.

    Returns:
        Number of chunks ingested (usually 1).
    """
    doc = Document(
        page_content=description,
        metadata={
            "source": image_filename,
            "user_id": user_id,
            "file_type": "image",
            **(metadata or {}),
        },
    )

    vector_store.add_documents([doc])
    print(f"✅ Ingested image description: {image_filename}")
    return 1


def delete_user_documents(user_id: str) -> bool:
    """
    Delete all documents belonging to a specific user.
    Note: langchain-postgres PGVector doesn't natively support filtered delete,
    so this uses a direct SQL query.

    Fix #7: Uses module-level _sql_engine (shared pool) instead of
    creating a new engine per call.

    Args:
        user_id: The user whose documents to delete.

    Returns:
        True if successful.
    """
    try:
        from sqlalchemy import text
        with _sql_engine.connect() as conn:
            conn.execute(
                text(
                    "DELETE FROM langchain_pg_embedding "
                    "WHERE cmetadata->>'user_id' = :uid"
                ),
                {"uid": user_id},
            )
            conn.commit()
        print(f"🗑️ Deleted all documents for user {user_id}")
        return True
    except Exception as e:
        print(f"⚠️ Error deleting user documents: {e}")
        return False
