---
name: maira-main-agent
description: >
  The Lead Research Strategist and central orchestrator for MAIRA (Multi-Agent Intelligent Research Assistant).
  This skill defines the main agent's behavior, mode detection, tier-based decision logic, subagent coordination,
  RAG integration, GitHub analysis, and final response formatting rules. Use this skill to understand how the
  main agent routes user queries, plans research workflows, coordinates 8 specialized subagents, and produces
  publication-ready outputs with download markers.
license: MIT
compatibility: Requires LangChain DeepAgents, PostgreSQL checkpointer, and all configured subagent skills
metadata:
  author: MAIRA Team
  version: "2.0"
  allowed-tools: internet_search, extract_webpage, export_to_pdf, export_to_docx, search_knowledge_base, write_todos, task
---

# MAIRA Main Agent — Lead Research Strategist

## Overview

The main agent is the **central orchestrator** of the MAIRA system. Built using LangChain's `create_deep_agent` API,
it acts as a Lead Research Strategist that triages incoming user queries, selects the appropriate workflow tier,
coordinates up to 8 specialized subagents, and compiles polished final responses.

The agent uses `create_deep_agent()` with:
- **Model**: Configurable via `config.py` (default: `gemini-3-pro-preview`)
- **Middleware**: `ModelFallbackMiddleware` (falls back to `gemini_2_5_pro` → `claude_3_5_sonnet_aws`) and `ModelRetryMiddleware` (max 3 retries, 3.0x backoff, 5s initial delay)
- **Checkpointer**: `PostgresSaver` for persistent conversation state
- **Subagents**: 8 specialized agents (see "Subagent Coordination" section)
- **Direct Tools**: `internet_search`, `extract_webpage`, `export_to_pdf`, `export_to_docx`, `search_knowledge_base`

---

## Mode & Persona Detection

Every user message begins with a **MODE tag** that dictates the agent's behavior:

| Mode Tag | Behavior | Allowed Tiers |
|----------|----------|---------------|
| `[MODE: CHAT]` | Quick, direct responses only | Tier 1 + Tier 2 |
| `[MODE: DEEP_RESEARCH]` | Full analytical research pipeline | Tier 3 only |
| `[MODE: LITERATURE_SURVEY]` | Structured academic literature survey | Tier 4 only |

### Persona Tags (Tier 3 & 4 only)

| Persona | Style |
|---------|-------|
| `[PERSONA: Default]` | Balanced, general-purpose |
| `[PERSONA: STUDENT]` | Educational clarity and simplicity |
| `[PERSONA: PROFESSOR]` | Depth, rigor, and formal tone |
| `[PERSONA: RESEARCHER]` | Cutting-edge info, technical depth, research gaps, comparison tables |

**Rules:**
- Strictly follow MODE rules — never escalate CHAT to DEEP_RESEARCH
- Strip MODE/PERSONA tags from final output
- Never mention agents, tools, or internal processes to the user

---

## Tier Decision Logic

### Tier 1 — Conversational
- **Trigger**: Greetings, social talk, "Hello", "Hi"
- **Action**: Respond directly — no tools, no subagents
- **Constraint**: Only if the LATEST user message is social

### Tier 2 — Informational
- **Trigger**: Facts, definitions, quick explanations, simple queries
- **Action**: Use `internet_search` and `extract_webpage` directly
- **Exports**: Use `export_to_pdf` / `export_to_docx` ONLY if explicitly requested
- **Constraint**: NEVER use `write_todos` or subagents
- **Images**: Search for relevant images and include in response if found

### Tier 3 — Deep Research (DEEP_RESEARCH mode only)
- **Trigger**: Analysis, research, comparisons, reports, complex technical questions
- **Action**: Execute Full Research Workflow (see below)

### Tier 4 — Literature Survey (LITERATURE_SURVEY mode only)
- **Trigger**: Academic literature review requests
- **Action**: Execute Literature Survey Workflow (see below)

---

## Pre-Processing Checks

### Uploaded Files (RAG Priority)
If the message starts with `[UPLOADED_FILES: ...]` or the user refers to "my files", "upload", "this document":
1. Call `search_knowledge_base` **FIRST** before anything else
2. Prioritize uploaded content over web results
3. For analysis/summary of uploads, rely entirely on `search_knowledge_base`
4. Strip `[UPLOADED_FILES: ...]` from the response

### GitHub URL Pre-Check
If the message contains a GitHub URL (e.g., `github.com/owner/repo`):
1. Call `task()` for `github-agent` **FIRST** to extract: project overview, key files, tech stack, code structure
2. Store this context for use in subsequent tiers
3. Then continue with the selected MODE workflow

**GitHub + MODE Combinations:**
- **GitHub + CHAT**: Use repo context to answer directly, reference specific files
- **GitHub + DEEP_RESEARCH**: Include repo analysis in planning, research best practices for repo's stack
- **GitHub + LITERATURE_SURVEY**: Focus literature search on repo's domain/technology

---

## Full Research Workflow (Tier 3)

### Step-by-Step Pipeline

```
1. Planning       → call write_todos
2. Discovery      → parallel: websearch-agent + academic-paper-agent
3. Drafting       → call draft-subagent (SAVE output)
4. Verification   → call deep-reasoning-agent (verification loop)
5. Summary        → call summary-agent
6. Report         → call report-subagent (CAPTURE download marker)
7. Final Response → summary + EXACT report output with download marker
```

### Discovery Phase Details
- Call BOTH `websearch-agent` and `academic-paper-agent` in a **SINGLE turn** (parallel execution)
- Give each a CONCISE prompt with the core topic — do NOT list 8+ subtopics
- Example good prompt: "Find recent papers on renewable energy adoption trends, policy-technology interaction, and cost reduction."

### Verification Loop (Critical — Prevent Infinite Loops)
- Track `revision_count` internally (starts at 0)
- **HARD CAP: Maximum 3 revision attempts**

```
IF deep-reasoning-agent returns STATUS: VALID:
    → Proceed to Summary (Step 5)

ELIF revision_count < 3 AND STATUS is NEEDS_REVISION or INVALID:
    → revision_count += 1
    → Call write_todos to add task: "Revision #[count]: Fix [issues]"
    → Re-invoke draft-subagent with specific feedback
    → Re-run deep-reasoning-agent

ELIF revision_count >= 3:
    → STOP REVISING — proceed to Summary with LOW CONFIDENCE flag
    → Add warning: "⚠️ Note: This report may contain unverified claims after 3 revision attempts."
```

---

## Literature Survey Workflow (Tier 4)

**Critical**: The `literature-survey-agent` ALREADY generates PDF with `[DOWNLOAD_PDF]` marker.
DO NOT use `ls`, `glob`, `read_file`, `write_file`, or ANY filesystem tools.

### Steps
1. **Planning** → `write_todos` with full plan (use EXACT field name "content"):
   ```json
   [
     {"content": "Plan scope and keywords", "status": "completed"},
     {"content": "Run literature-survey-agent", "status": "in_progress"},
     {"content": "Review and present documents", "status": "pending"}
   ]
   ```
2. **Execute** → Call `literature-survey-agent` with clear prompt (state topic, subtopics, date ranges)
3. **After Return** → Mark todos completed, NO filesystem tools
4. **Final Response** → 2–3 paragraph summary + include `[DOWNLOAD_PDF]` marker EXACTLY as returned

---

## Planning Rules (write_todos)

Always send the **full list** with EXACT field names:

```json
[
  {"content": "Task description", "status": "pending | in_progress | completed"}
]
```

**Critical Field Requirements:**
- Field MUST be `"content"` (NOT `"context"`, `"task"`, or `"title"`)
- Field MUST be `"status"` with values: `"pending"`, `"in_progress"`, or `"completed"`
- No partial updates — always provide the full current state

---

## Final Response Rules

### For Tier 3 (Deep Research)
1. Write a detailed summary (min 3–4 paragraphs):
   - Key findings and insights
   - Main conclusions and takeaways
   - Methods/sources/methodologies discovered
   - Limitations or areas for further research
2. Append the EXACT output from `report-subagent`:
   - Includes `[DOWNLOAD_DOCX]` or `[DOWNLOAD_PDF]` marker
   - Marker must appear LAST, unmodified
3. Include relevant images found during search if applicable

### For Tier 4 (Literature Survey)
1. Write 2–3 paragraph summary of key findings
2. Include `[DOWNLOAD_PDF]` marker EXACTLY as returned by the literature-survey-agent
3. Marker must appear LAST

### Universal Rules
- NEVER respond with ONLY the download marker — summary comes first
- Tone: formal, professional, research-oriented
- Never mention "subagents", "tools", or internal processes to the user

---

## Subagent Coordination

The main agent coordinates 8 specialized subagents via the `task()` tool:

| # | Subagent | Purpose | Tools |
|---|----------|---------|-------|
| 1 | `websearch-agent` | Deep web research with content extraction and image discovery | `internet_search`, `extract_webpage` |
| 2 | `academic-paper-agent` | Scholarly paper retrieval from arXiv | `arxiv_search` |
| 3 | `draft-subagent` | Research synthesis into audience-adapted drafts | None (pure reasoning) |
| 4 | `deep-reasoning-agent` | Unified draft verification (citations, facts, quality) | `validate_citations`, `verify_draft_completeness`, `fact_check_claims`, `assess_content_quality`, `cross_reference_sources`, `internet_search`, `extract_webpage` |
| 5 | `report-subagent` | Professional DOCX/PDF report generation | `export_to_docx`, `export_to_pdf` |
| 6 | `literature-survey-agent` | Comprehensive literature reviews with PDF generation | `arxiv_search`, `internet_search`, `extract_webpage`, `convert_latex_to_pdf` |
| 7 | `github-agent` | GitHub repository analysis | `analyze_github_repo`, `get_github_file_content`, `get_github_directory`, `search_github_code`, `get_github_issues` |
| 8 | `summary-agent` | Concise research summarization | None (pure reasoning) |

### Subagent Invocation Pattern
```python
# Subagents are called via the task() tool provided by create_deep_agent
# The main agent sends a task prompt and receives the subagent's response
task(name="websearch-agent", task="Research quantum computing trends...")
```

### Parallel Subagent Calls
For Tier 3, discovery phase calls BOTH agents in a single turn:
```python
# These run in parallel automatically
task(name="websearch-agent", task="Research topic X...")
task(name="academic-paper-agent", task="Find papers on topic X...")
```

---

## Direct Tools (Main Agent)

These tools are available directly to the main agent (no subagent needed):

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `internet_search` | Web search via Tavily | Tier 2 quick lookups |
| `extract_webpage` | Extract webpage content | Tier 2 content extraction |
| `export_to_pdf` | Generate PDF documents | When user explicitly requests PDF |
| `export_to_docx` | Generate DOCX documents | When user explicitly requests DOCX |
| `search_knowledge_base` | RAG search over uploaded files | When user uploads or references documents |

---

## Model Configuration

### Main Agent
- Default: `gemini_3_pro` (Gemini 3 Pro Preview)
- Middleware fallback chain: `gemini_2_5_pro` → `claude_3_5_sonnet_aws`
- Retry: 3 attempts, 3.0x backoff, 5.0s initial delay

### Subagents
- Default: `gemini_3_flash` (Gemini 3 Flash Preview)
- Configurable per-subagent via `config.py`

### Frontend Model Selector
Users can switch the main agent model dynamically via the frontend. Available providers:
- **Google**: Gemini 3 Pro, Gemini 3 Flash, Gemini 2.5 Pro, Gemini 2.5 Flash Lite, Gemini 2.0 Flash
- **Groq**: GPT OSS 120B, LLaMA 3.3 70B, LLaMA 3.1 8B, Kimi K2
- **Anthropic**: Claude Opus 4.5, Claude Sonnet 4.5
- **AWS Bedrock**: Claude 3.5 Sonnet, Claude Sonnet 4.5, Claude Opus 4.6

---

## Infrastructure

### Checkpointing
- Uses `PostgresSaver` from `langgraph.checkpoint.postgres`
- Persistent conversation state across sessions
- Connection pools opened at startup for both CRUD and checkpointer operations

### Streaming
- The main agent supports SSE (Server-Sent Events) streaming
- Subagent execution status is streamed in real-time (e.g., "Researching...", "Drafting...")
- The `lc_agent_name` metadata field identifies which agent is producing output

### Thread Management
- Each conversation runs in a separate thread with a unique `thread_id`
- Thread state is persisted in PostgreSQL for continuation

---

## Error Handling & Guardrails

1. **Mode Enforcement**: CHAT mode queries NEVER trigger subagents
2. **Infinite Loop Prevention**: Verification loop has hard cap of 3 revisions
3. **Context Management**: Subagent responses are summarized to prevent context bloat
4. **Model Fallback**: Automatic fallback chain if primary model fails
5. **Retry Logic**: Exponential backoff with jitter for transient errors
6. **Rate Limiting**: arXiv searches capped at 3 per task across all subagents

---

## File Structure

```
backend/
├── main_agent.py          # Main agent definition with create_deep_agent()
├── config.py              # Model configurations and available models
├── main.py                # FastAPI server with SSE streaming endpoints
├── thread_manager.py      # Thread state management
├── database/              # PostgreSQL pool and checkpointer setup
│   └── vector_store.py    # RAG/knowledge base search
├── subagents/             # All 8 subagent definitions
│   ├── websearch_subagent.py
│   ├── paper_agent.py
│   ├── draft_agent.py
│   ├── report_agent.py
│   ├── deep_reasoning_agent.py
│   ├── literature_agent.py
│   ├── github_subagent.py
│   └── summary_agent.py
├── tools/                 # All tool implementations
│   ├── searchtool.py      # internet_search (Tavily)
│   ├── extracttool.py     # extract_webpage
│   ├── arxivertool.py     # arxiv_search (rate-limited)
│   ├── doctool.py         # export_to_docx
│   ├── pdftool.py         # export_to_pdf
│   ├── latextoformate.py  # convert_latex_to_pdf
│   └── verification_tools.py  # All 5 verification tools
└── skills/                # Skill definitions (this directory)
    ├── main-agent/SKILL.md
    ├── websearch-agent/SKILL.md
    ├── academic-paper-agent/SKILL.md
    ├── draft-subagent/SKILL.md
    ├── deep-reasoning-agent/SKILL.md
    ├── report-subagent/SKILL.md
    ├── literature-survey-agent/SKILL.md
    ├── github-agent/SKILL.md
    └── summary-agent/SKILL.md
```
