# MAIRA — Multi-Agent Intelligent Research Assistant

MAIRA is an AI-powered deep research platform that orchestrates multiple specialized agents to perform comprehensive research, literature surveys, and professional report generation. It features a modern React chat interface with real-time SSE streaming, Supabase authentication, document uploads with RAG retrieval, GitHub repository analysis, and multi-model support across Google, Anthropic, Meta, and Moonshot providers.

---

## Features

### Multi-Tier Research System
- **Tier 1 — Conversational**: Greetings and simple interactions
- **Tier 2 — Informational**: Quick web searches, facts, and data lookups
- **Tier 3 — Deep Research**: Full multi-agent orchestration with drafting, verification loops, and report generation
- **Tier 4 — Literature Survey**: Structured academic literature reviews with LaTeX-to-PDF/DOCX generation
- **Tier 5 — Paper Writer**: Full-featured LaTeX editor with AI assistance, live preview, and client-side export (PDF/DOCX)

### Specialized Agents
| Agent | Responsibility |
|-------|---------------|
| **Web Search** | Internet research via Tavily + webpage content extraction |
| **Academic Paper** | arXiv paper retrieval with rate limiting |
| **Draft** | Structured research synthesis with comparison tables |
| **Deep Reasoning** | Citation validation, fact-checking, quality assessment |
| **Validation** | Citation format checking, URL accessibility, completeness verification |
| **Fact-Checking** | Factual claim verification against sources |
| **Quality Checking** | Content quality assessment and source utilization scoring |
| **Summary** | Concise summary generation from draft outputs |
| **Report** | Professional report formatting and export (PDF/DOCX) |
| **Literature Survey** | LaTeX-based academic literature reviews → PDF/DOCX |
| **Paper Writer** | Dedicated LaTeX editor with template selection and AI chat |
| **GitHub** | Repository analysis (structure, tech stack, code review) via GitHub App |

### Multi-Model Support
Switch between LLMs from the frontend:
- **Google Gemini**: 3 Pro, 3 Flash, 2.5 Pro, 2.5 Flash Lite, 2.0 Flash
- **Anthropic Claude**: Opus 4.5, Sonnet 4.5 (direct API); Opus 4.6, Sonnet 4.5, 3.5 Sonnet (via AWS Bedrock)
- **Meta LLaMA**: 3.3 70B Versatile, 3.1 8B Instant (via Groq)
- **Moonshot Kimi K2 Instruct**, **GPT OSS 120B** (via Groq)

> **Default model**: Claude Opus 4.6 AWS — configurable in `config.py`

### Verification Pipeline
Deep Research (Tier 3) includes an automated verification loop:
1. **Validation Agent** — checks citation format, URL accessibility, and completeness
2. **Fact-Checking Agent** — verifies factual claims against gathered sources
3. **Quality-Checking Agent** — assesses content quality and source utilization
4. Revision loop with a hard cap of 3 attempts; proceeds with a low-confidence warning if issues persist

### Document Pipeline
- Upload `.pdf`, `.doc`, `.docx`, and image files
- User-scoped RAG retrieval via Supabase PGVector + Google Gemini embeddings
- Auto-read uploaded documents (ChatGPT-style)
- Generate PDF/DOCX reports via LaTeX compilation (pdflatex → xelatex → pandoc fallback)
- In-chat download buttons for generated documents (separate styling for PDF and DOCX)

### Authentication & Persistence
- Supabase Auth (email/password, OAuth)
- Per-user thread management with UUID v7
- PostgreSQL-backed chat history via LangGraph checkpoints
- User-scoped document storage and retrieval
- Upstash Redis for caching and rate limiting

### Chat Interface
- Real-time SSE streaming with automatic reconnection
- Deep Research progress tracker with step-by-step timeline
- Deep Reasoning mode with expandable thinking blocks
- Verification scores and badges
- Speech-to-text input
- Thread sidebar with search
- Model selector dropdown
- Thread branching from checkpoints
- Attachment chips for uploaded files
- Markdown rendering with syntax highlighting, GitHub Flavored Markdown, and LaTeX math
- Toast notifications via Sonner

---

## Architecture

```
agent/
├── README.md
├── backend/                        # Python / FastAPI
│   ├── main.py                     # API server, SSE streaming, session management
│   ├── main_agent.py               # Lead Research Strategist (orchestrator)
│   ├── config.py                   # Model registry and LLM configuration
│   ├── thread_manager.py           # Thread/conversation CRUD
│   ├── latexagent.py               # LaTeX document generation chain
│   ├── security.py                 # Security utilities
│   ├── requirements.txt            # Python dependencies
│   ├── database/
│   │   ├── __init__.py             # Pool management and checkpointer factory
│   │   ├── postgres.py             # Supabase PostgreSQL connection pool
│   │   ├── schema.sql              # Full DB schema (UUID v7, pgvector)
│   │   └── vector_store.py         # RAG: embedding + retrieval
│   ├── subagents/
│   │   ├── websearch_subagent.py       # Web search orchestration
│   │   ├── paper_agent.py              # arXiv paper retrieval
│   │   ├── draft_agent.py              # Research synthesis and drafting
│   │   ├── deep_reasoning_agent.py     # Deep reasoning and analysis
│   │   ├── validation_subagent.py      # Citation and completeness validation
│   │   ├── fact_checking_subagent.py   # Factual claim verification
│   │   ├── quality_checking_subagent.py# Content quality assessment
│   │   ├── summary_agent.py            # Draft summary generation
│   │   ├── report_agent.py             # Report formatting and export
│   │   ├── literature_agent.py         # Literature survey workflow
│   │   └── github_subagent.py          # GitHub repository analysis
│   ├── tools/
│   │   ├── __init__.py             # Tool registry and exports
│   │   ├── searchtool.py           # Tavily web search
│   │   ├── arxivertool.py          # arXiv API with rate limiting
│   │   ├── extracttool.py          # Webpage content extraction
│   │   ├── crawltool.py            # Web crawling utility
│   │   ├── latextoformate.py       # LaTeX → PDF/DOCX/MD (pdflatex + pandoc)
│   │   ├── pdftool.py              # PDF export
│   │   ├── doctool.py              # DOCX export
│   │   ├── generatedoc.py          # Document generation wrapper
│   │   ├── generatelargedoc.py     # Large document chunked generation
│   │   ├── splittool.py            # Text splitting
│   │   └── verification_tools.py   # Citation, fact-check, quality tools
│   ├── tests/
│   │   ├── list_tables.py          # Database table listing
│   │   ├── setup_schema.py         # Schema setup script
│   │   └── setup_async_schema.py   # Async schema setup script
│   ├── exports/                    # Generated report output directory
│   └── storage/                    # File storage directory
└── frontend/                       # React + TypeScript
    └── MAIRA/
        └── src/
            ├── App.tsx                        # Root app with routing
            ├── main.tsx                       # Entry point
            ├── index.css                      # Global styles
            ├── App.css                        # App-level styles
            ├── components/
            │   ├── index.ts                   # Barrel exports
            │   ├── ChatArea.tsx               # Main chat view
            │   ├── MessageBubble.tsx          # Message rendering + downloads
            │   ├── Sidebar.tsx                # Thread list + search
            │   ├── ModelSelector.tsx          # LLM picker dropdown
            │   ├── ReasoningBlock.tsx         # Expandable thinking UI
            │   ├── DeepResearchProgress.tsx   # Research step progress tracker
            │   ├── TimelineView.tsx           # Research step timeline
            │   ├── BranchSwitcher.tsx         # Thread branch navigation
            │   ├── ProtectedRoute.tsx         # Auth route guard
            │   ├── VerificationBadge.tsx      # Quality score badge
            │   └── VerificationScore.tsx      # Detailed score breakdown
            ├── context/
            │   ├── AuthContext.tsx             # Supabase auth state
            │   ├── ThreadContext.tsx           # Threads, messages, streaming
            │   └── ThreadContextDefinition.ts # Type definitions for context
            ├── pages/
            │   ├── Home.tsx                   # Main app page
            │   ├── Login.tsx                  # Auth login
            │   └── Signup.tsx                 # Auth signup
            ├── hooks/
            │   ├── useSpeechRecognition.ts    # Browser speech-to-text
            │   ├── useStreamWithReconnect.ts  # SSE stream with auto-reconnect
            │   ├── useThreadIDParam.ts        # URL thread ID parameter
            │   └── useThreads.ts              # Thread management hook
            ├── lib/
            │   ├── supabase.ts                # Supabase client initialization
            │   └── utils.ts                   # Utility functions
            └── types/
                └── agent.ts                   # Agent-related type definitions
```

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **PostgreSQL** (Supabase recommended)
- **LaTeX distribution** (TeX Live or MiKTeX) — for PDF generation
- **Pandoc** — for document format conversion

### API Keys & Environment Variables

| Service | Environment Variable | Purpose |
|---------|---------------------|---------|
| Google Gemini | `GEMINI_API_KEY` | Primary LLM + embeddings |
| Groq | `GROQ_API_KEY` | LLaMA, Kimi K2, GPT OSS models |
| Anthropic | `ANTHROPIC_API_KEY` | Claude Opus/Sonnet (direct API) |
| AWS Bedrock | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Claude models via Bedrock |
| Tavily | `TAVILY_API_KEY` | Web search |
| Supabase | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABSE_SERVICE_KEY` | Auth, database, vector store |
| Upstash Redis | `UPSTASH_REDIS_URL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` | Caching and rate limiting |
| Qdrant | `QDRANT_API_KEY`, `QDRANT_ENDPOINT` | Vector database |
| GitHub App | `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_REPOSITORY` | Repository analysis |
| LangSmith | `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT` | Tracing and observability |
| Mistral | `MISTRAL_API_KEY` | Mistral embeddings (optional) |
| OpenAI | `OPENAI_API_KEY` | OpenAI-compatible endpoints (optional) |

### Backend Setup

```bash
cd agent/backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env         # Edit with your API keys

# Start the server
uvicorn main:app --reload --port 8000
```

### Frontend Setup

```bash
cd agent/frontend/MAIRA

npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.

### Database Setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Run `database/schema.sql` in the Supabase SQL editor
3. Enable the `pgvector` extension
4. Add your Supabase URL and keys to `.env`
5. Optionally run `tests/setup_schema.py` to verify tables

---

## API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/users/sync` | Sync user from Supabase Auth |
| `GET` | `/users/{user_id}` | Get user profile |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/documents/upload` | Upload PDF/DOC/DOCX files (with RAG embedding) |
| `POST` | `/documents/upload-image` | Upload image files |
| `DELETE` | `/documents/{user_id}` | Delete user's documents |

### Models
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/models` | List available LLMs |
| `GET` | `/models/current` | Get currently selected model |
| `POST` | `/models/select` | Switch active model |

### Threads
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/threads` | Create new conversation thread |
| `GET` | `/threads` | List all threads for user |
| `GET` | `/threads/{thread_id}` | Get thread details |
| `PUT` | `/threads/{thread_id}` | Update thread title |
| `DELETE` | `/threads/{thread_id}` | Delete thread and all messages |
| `GET` | `/threads/{thread_id}/messages` | Get thread messages |
| `GET` | `/threads/{thread_id}/history` | Get full conversation history |
| `POST` | `/threads/{thread_id}/branch` | Branch from a checkpoint |

### Agent Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/run-agent` | Start agent session (returns SSE stream) |
| `GET` | `/sessions/{thread_id}/stream` | SSE event stream |
| `GET` | `/sessions/{thread_id}/status` | Check session status |
| `POST` | `/sessions/{thread_id}/cancel` | Cancel running session |

### Request Format
```json
{
  "prompt": "Your research question",
  "thread_id": "uuid-v7-thread-id",
  "user_id": "supabase-user-id",
  "deep_research": false,
  "literature_survey": false,
  "persona": "default",
  "model": "anthropic.claude-opus-4-6-v1"
}
```

---

## Technologies

### Backend
| Technology | Purpose |
|-----------|---------|
| FastAPI | HTTP API + SSE streaming |
| LangGraph | Agent state machine + checkpoints |
| LangChain | LLM orchestration + tool binding |
| DeepAgents | Multi-agent deep research framework |
| Supabase (PostgreSQL) | Auth, threads, messages, vector store |
| PGVector | Embedding storage for RAG |
| Qdrant | Cloud vector database |
| Upstash Redis | Caching + rate limiting |
| pypandoc | LaTeX/document format conversion |
| pdflatex/xelatex | Direct LaTeX → PDF compilation |
| python-docx / ReportLab | DOCX and PDF generation |
| PyGithub | GitHub App integration |

### Frontend
| Technology | Purpose |
|-----------|---------|
| React 19 | UI framework |
| TypeScript 5.9 | Type safety |
| Rolldown Vite | Build tool + HMR |
| Tailwind CSS 4 | Styling |
| Framer Motion | Animations |
| Supabase JS | Auth client |
| React Router 7 | Client-side routing |
| React Markdown + remark-gfm | Markdown + GFM rendering |
| Lucide React | Icons |
| Sonner | Toast notifications |
| Axios | HTTP client |
| jsPDF | Client-side PDF generation |
| docx | Client-side Word document generation |

### Infrastructure & Middleware
| Technology | Purpose |
|-----------|---------|
| ModelFallbackMiddleware | Automatic fallback between LLM providers |
| ModelRetryMiddleware | Retry with exponential backoff on transient errors |
| LangSmith | Tracing, debugging, and observability |

---

## Usage

### Chat Mode
Ask any question — MAIRA responds directly using web search when needed. Supports file uploads for RAG-powered Q&A.

### Deep Research Mode
Toggle "Deep Research" for complex multi-step analysis:
1. MAIRA plans the research with a structured todo list
2. Web search + arXiv agents gather sources in parallel
3. Draft agent synthesizes findings with comparison tables
4. **Verification loop** — validation, fact-checking, and quality-checking agents review the draft (up to 3 revision cycles)
5. Summary agent generates a concise overview
6. Report agent produces a downloadable PDF/DOCX

### Literature Survey Mode
Toggle "Literature Survey" for academic reviews:
1. Agent searches arXiv for relevant papers
2. Compiles structured LaTeX with comparison tables
3. Generates PDF for download directly in the chat

### Paper Writer
Access the specialized writing environment for drafting papers:
1. **Templates**: proper IEEE, Research Article, and Thesis templates
2. **Editor**: Split-view editor with LaTeX syntax highlighting and live preview
3. **AI Assistance**: Chat with the contextual AI to write sections, fix errors, or rephrase text
4. **Export**: Instant client-side export to PDF and Word formats

### Document Upload
Drag & drop or click to upload `.pdf`, `.doc`, `.docx` files. MAIRA automatically reads and indexes the content for RAG-powered Q&A. Uploaded documents are prioritized over web search results when answering questions.

### GitHub Analysis
Paste a GitHub repository URL in your message. MAIRA analyzes the repo structure, tech stack, and code via the installed GitHub App before answering your question. Works in combination with all modes (Chat, Deep Research, Literature Survey).

### Personas
Customize research output style:
- **Default** — Balanced tone
- **Student** — Educational clarity and simplicity
- **Professor** — Academic rigor and formality
- **Researcher** — Technical depth and novelty

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

This project is available for personal and educational use.

---

> **Security Note**: Never commit API keys to version control. Use `.env` files and add them to `.gitignore`.
