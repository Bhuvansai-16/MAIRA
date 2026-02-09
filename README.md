# MAIRA — Multi-Agent Intelligent Research Assistant

MAIRA is an AI-powered deep research platform that orchestrates multiple specialized agents to perform comprehensive research, literature surveys, and professional report generation. It features a modern React chat interface with real-time streaming, authentication, document uploads, and multi-model support.

---

## Features

### Multi-Tier Research System
- **Tier 1 — Conversational**: Greetings and simple interactions
- **Tier 2 — Informational**: Quick web searches, facts, and data lookups
- **Tier 3 — Deep Research**: Full multi-agent orchestration with drafting, verification, and report generation
- **Tier 4 — Literature Survey**: Structured academic literature reviews with LaTeX-to-PDF/DOCX generation

### Specialized Agents
| Agent | Responsibility |
|-------|---------------|
| **Web Search** | Internet research via Tavily + webpage content extraction |
| **Academic Paper** | arXiv paper retrieval with rate limiting |
| **Draft** | Structured research synthesis with comparison tables |
| **Deep Reasoning** | Citation validation, fact-checking, quality assessment |
| **Report** | Professional report formatting and export |
| **Literature Survey** | LaTeX-based academic literature reviews → PDF/DOCX |
| **GitHub** | Repository analysis (structure, tech stack, code review) |

### Multi-Model Support
Switch between LLMs from the frontend:
- **Google Gemini**: 3 Pro, 3 Flash, 2.5 Pro, 2.5 Flash Lite, 2.0 Flash
- **Anthropic Claude**: Opus 4.5, Sonnet 4.5, 3.5 Sonnet (via AWS Bedrock)
- **Meta LLaMA**: 3.3 70B, 3.1 8B (via Groq)
- **Moonshot Kimi K2**, **GPT OSS 120B** (via Groq)

### Document Pipeline
- Upload `.pdf`, `.doc`, `.docx`, and image files
- User-scoped RAG retrieval via Supabase PGVector + Google Gemini embeddings
- Auto-read uploaded documents (ChatGPT-style)
- Generate PDF/DOCX reports via LaTeX compilation (pdflatex → xelatex → pandoc fallback)
- In-chat download buttons for generated documents

### Authentication & Persistence
- Supabase Auth (email/password, OAuth)
- Per-user thread management with UUID v7
- PostgreSQL-backed chat history via LangGraph checkpoints
- User-scoped document storage and retrieval

### Chat Interface
- Real-time SSE streaming with tool status indicators
- Deep Reasoning mode with expandable thinking blocks
- Verification scores and badges
- Speech-to-text input
- Thread sidebar with search
- Model selector dropdown
- Attachment chips for uploaded files
- Markdown rendering with syntax highlighting and LaTeX math

---

## Architecture

```
agent/
├── backend/                    # Python / FastAPI
│   ├── main.py                 # API server, SSE streaming, session management
│   ├── main_agent.py           # Lead Research Strategist (orchestrator)
│   ├── config.py               # Model registry and LLM configuration
│   ├── thread_manager.py       # Thread/conversation CRUD
│   ├── database/
│   │   ├── postgres.py         # Supabase PostgreSQL connection pool
│   │   ├── schema.sql          # Full DB schema (UUID v7, pgvector)
│   │   └── vector_store.py     # RAG: embedding + retrieval
│   ├── subagents/
│   │   ├── websearch_subagent.py
│   │   ├── paper_agent.py
│   │   ├── draft_agent.py
│   │   ├── deep_reasoning_agent.py
│   │   ├── report_agent.py
│   │   ├── literature_agent.py
│   │   └── github_subagent.py
│   └── tools/
│       ├── searchtool.py       # Tavily web search
│       ├── arxivertool.py      # arXiv API with rate limiting
│       ├── extracttool.py      # Webpage content extraction
│       ├── latextoformate.py   # LaTeX → PDF/DOCX/MD (pdflatex + pandoc)
│       ├── pdftool.py          # PDF export
│       ├── doctool.py          # DOCX export
│       ├── generatedoc.py      # Document generation wrapper
│       ├── generatelargedoc.py # Large document chunked generation
│       ├── splittool.py        # Text splitting
│       └── verification_tools.py # Citation, fact-check, quality tools
└── frontend/                   # React + TypeScript
    └── MAIRA/
        └── src/
            ├── components/
            │   ├── ChatArea.tsx           # Main chat view
            │   ├── MessageBubble.tsx      # Message rendering + downloads
            │   ├── Sidebar.tsx            # Thread list + search
            │   ├── ModelSelector.tsx      # LLM picker dropdown
            │   ├── ReasoningBlock.tsx     # Expandable thinking UI
            │   ├── TimelineView.tsx       # Research step timeline
            │   ├── VerificationBadge.tsx  # Quality score badge
            │   └── VerificationScore.tsx  # Detailed score breakdown
            ├── context/
            │   ├── AuthContext.tsx         # Supabase auth state
            │   └── ThreadContext.tsx       # Threads, messages, streaming
            ├── pages/
            │   ├── Home.tsx               # Main app page
            │   ├── Login.tsx              # Auth login
            │   └── Signup.tsx             # Auth signup
            └── hooks/
                ├── useSpeechRecognition.ts
                └── useThreads.ts
```

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **PostgreSQL** (Supabase recommended)
- **LaTeX distribution** (TeX Live or MiKTeX) — for PDF generation
- **Pandoc** — for document format conversion

### API Keys Required

| Service | Environment Variable | Purpose |
|---------|---------------------|---------|
| Google Gemini | `GOOGLE_API_KEY` | Primary LLM + embeddings |
| Groq | `GROQ_API_KEY` | LLaMA, Kimi, GPT OSS models |
| Anthropic | `ANTHROPIC_API_KEY` | Claude models |
| AWS Bedrock | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Claude 3.5 Sonnet |
| Tavily | `TAVILY_API_KEY` | Web search |
| Supabase | `SUPABASE_URL`, `SUPABASE_KEY` | Auth, database, vector store |
| GitHub | `GITHUB_TOKEN` | Repository analysis (optional) |

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
4. Add your Supabase URL and anon key to `.env`

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
| `POST` | `/run-agent` | Start agent session |
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
  "model": "gemini-3-pro-preview"
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
| DeepAgents | Multi-agent framework |
| Supabase (PostgreSQL) | Auth, threads, messages, vector store |
| PGVector | Embedding storage for RAG |
| pypandoc | LaTeX/document format conversion |
| pdflatex/xelatex | Direct LaTeX → PDF compilation |

### Frontend
| Technology | Purpose |
|-----------|---------|
| React 19 | UI framework |
| TypeScript | Type safety |
| Vite | Build tool + HMR |
| Tailwind CSS 4 | Styling |
| Framer Motion | Animations |
| Supabase JS | Auth client |
| React Router 7 | Client-side routing |
| React Markdown | Markdown + GFM rendering |

---

## Usage

### Chat Mode
Ask any question — MAIRA responds directly using web search when needed.

### Deep Research Mode
Toggle "Deep Research" for complex multi-step analysis:
1. MAIRA plans the research with a todo list
2. Web search + arXiv agents gather sources in parallel
3. Draft agent synthesizes findings
4. Deep reasoning agent validates citations and facts
5. Report agent generates a downloadable PDF/DOCX

### Literature Survey Mode
Toggle "Literature Survey" for academic reviews:
1. Agent searches arXiv for relevant papers
2. Compiles structured LaTeX with comparison tables
3. Generates PDF and DOCX for download

### Document Upload
Drag & drop or click to upload `.pdf`, `.doc`, `.docx` files. MAIRA automatically reads and indexes the content for RAG-powered Q&A.

### GitHub Analysis
Paste a GitHub repository URL in your message. MAIRA analyzes the repo structure, tech stack, and code before answering your question.

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
