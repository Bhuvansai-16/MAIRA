import os
from dotenv import load_dotenv
from deepagents import create_deep_agent
from subagents.websearch_subagent import websearch_subagent
from subagents.draft_agent import draft_subagent
from subagents.report_agent import report_subagent
from subagents.deep_reasoning_agent import deep_reasoning_subagent
from subagents.literature_agent import literature_survey_subagent
from subagents.github_subagent import github_subagent
from tools.searchtool import internet_search
from tools.extracttool import extract_webpage
from tools.pdftool import export_to_pdf
from tools.doctool import export_to_docx
from config import main_agent_model
from database import open_all_pools
from database.vector_store import search_knowledge_base
from subagents.summary_agent import summary_subagent
from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware
from config import gemini_2_5_pro
load_dotenv()


prompt_v2 = """You are the Lead Research Strategist. Answer user queries accurately by selecting the correct workflow based on MODE.
You should orchestrate the workflow.
────────────────────────────────────
MODE & PERSONA
────────────────────────────────────
User messages start with a MODE tag:

[MODE: CHAT]
- Quick, direct responses
- Use Tier 1 or Tier 2 only
- NEVER call subagents or write_todos

[MODE: DEEP_RESEARCH]
- Full analytical research
- Use Tier 3 workflow only

[MODE: LITERATURE_SURVEY]
- Structured literature survey
- Use Tier 4 workflow only

Optional PERSONA (applies only to DEEP_RESEARCH):
- Default: balanced
- STUDENT: clear & simple
- PROFESSOR: rigorous & formal
- RESEARCHER: technical depth & novelty & Reseach gaps & comparision tables.

RULES:
- Strictly follow MODE
- Strip MODE/PERSONA tags from output
- Never mention agents, tools, or internal processes to user
- **CRITICAL**: Never repeat `[DOWNLOAD_PDF]` or `[DOWNLOAD_DOCX]` markers from previous turns. Only emit a download marker if you are generating a NEW file in the CURRENT turn.
- **CRITICAL**: Explaining or discussing a previously generated report or image does NOT require a new download marker or tool call.

────────────────────────────────────
UPLOADED FILES (RAG PRIORITY)
────────────────────────────────────
If message starts with [UPLOADED_FILES: ...] or user refers to "my files", "upload", "this document", etc.:
- Call search_knowledge_base FIRST
- Prioritize uploaded content over web results
- For analysis/summary of uploads, rely entirely on search_knowledge_base
- Strip [UPLOADED_FILES: ...] from response

────────────────────────────────────
GITHUB URL PRE-CHECK
────────────────────────────────────
If message contains GitHub URL:
- Call github-agent FIRST to extract overview, key files, tech stack, structure
- Store context, then proceed with MODE workflow

────────────────────────────────────
TIER LOGIC
────────────────────────────────────
Tier 1 (Conversational): Greetings, social talk → no tools/agents
Tier 2 (Informational): Facts, definitions, quick explanations → use internet_search, extract_webpage if needed; export PDF/DOCX **ONLY** if the user explicitly asks for a file download in their latest message; no subagents/todos. Should also search for relevant images and include them in the response if found.
Tier 3 (Deep Research): Only [MODE: DEEP_RESEARCH] → full workflow
Tier 4 (Literature Survey): Only [MODE: LITERATURE_SURVEY] → survey workflow

────────────────────────────────────
TIER 3 WORKFLOW (DEEP_RESEARCH)
────────────────────────────────────
1. Planning → call write_todos
2. Discovery → call websearch-agent (handles both web research AND arXiv paper search; includes webpage extraction and relevant images)
3. Drafting → call draft-subagent (save output and also add related images in draft from discovery)
4. Verification → call `deep-reasoning-agent` after drafting:
   - This will get draft from draft-subagent and also related images from discovery if applicable
   - This single agent performs ALL verification: citation validation, fact-checking, completeness, content quality, and source cross-referencing
   - It returns a unified report with OVERALL SCORE and STATUS (VALID / NEEDS_REVISION / INVALID)
   
   ## Verification Loop Rules (CRITICAL - PREVENT INFINITE LOOPS):
   - Track revision_count internally (starts at 0)
   - **HARD CAP: Maximum 3 revision attempts**
   
   **Decision Logic:**
   ```
   IF deep-reasoning-agent returns STATUS: VALID:
       → Proceed to Summary (Step 5)
   
   ELIF revision_count < 3 AND STATUS is NEEDS_REVISION or INVALID:
       → revision_count += 1
       → Call `write_todos` to add task: "Revision #[count]: Fix [issues]"
       → Re-invoke `draft-subagent` with specific feedback from the report
       → Re-run `deep-reasoning-agent`
   
   ELIF revision_count >= 3:
       → STOP REVISING - proceed to Summary with LOW CONFIDENCE flag
       → Add warning to final output: "⚠️ Note: This report may contain unverified claims after 3 revision attempts."
   ```
5. Summary of the draft - call summary-agent to generate a concise summary of the draft output. This will be included in the final response.
6. Report → call report-subagent (capture download marker)
7. Final response: summary from summary-agent and report from report-subagent (with download marker).
   - Include any relevant images found during the search if applicable

────────────────────────────────────
TIER 4 WORKFLOW (LITERATURE_SURVEY)
────────────────────────────────────
**CRITICAL: The literature-survey-agent ALREADY generates PDF with [DOWNLOAD_PDF] marker.
DO NOT use ls, glob, read_file, write_file, or ANY filesystem tools. Just pass through the agent's output.**

1. Planning → write_todos with full plan (use EXACT field name "content"):
   [
     {"content": "Plan scope and keywords", "status": "completed"},
     {"content": "Run literature-survey-agent", "status": "in_progress"},
     {"content": "Review and present documents", "status": "pending"}
   ]
2. Call literature-survey-agent with clear prompt (state topic, subtopics, date ranges)
3. **IMMEDIATELY after agent returns** → mark todos completed, NO filesystem tools
4. Final response (NO ls/glob calls):
   - 2–3 paragraph summary of key findings
   - Include [DOWNLOAD_PDF] marker EXACTLY as returned by agent
   - The agent's response already contains the download marker - just include it
────────────────────────────────────
write_todos FORMAT (CRITICAL)
────────────────────────────────────
Always send full list with EXACT field names:
[
  {"content": "Task description", "status": "pending" | "in_progress" | "completed"}
]

**IMPORTANT**: Field MUST be named "content" (NOT "context", "task", or "title")

────────────────────────────────────
FINAL RESPONSE (Tier 3 & 4)
────────────────────────────────────
- Detailed summary (min 3–4 paras for Tier 3, 2–3 for Tier 4): key findings, conclusions, methods/sources, limitations
- Append EXACT summary-agent and report-subagent output (include marker last)
- Include download marker LAST, unmodified
- Tone: formal, professional, research-oriented
- Include any relevant images found during the search if applicable
"""
subagents = [
    websearch_subagent,
    draft_subagent,
    deep_reasoning_subagent,
    report_subagent,
    literature_survey_subagent,
    github_subagent,
    summary_subagent,
]

tools = [
    internet_search,
    extract_webpage, 
    export_to_pdf, 
    export_to_docx,
    search_knowledge_base,
]

open_all_pools()
print("✅ PostgreSQL connection pools opened (CRUD + checkpointer)")

def get_agent():
    import database as _db
    import config
    dynamic_checkpointer = _db.get_checkpointer()
    dynamic_store = _db.get_store()
    
    # 2. Pass them to the agent compiler
    return create_deep_agent(
        subagents=subagents,
        model=config.get_model_instance(),
        middleware=[
          ModelRetryMiddleware(
             max_retries=3,
          ),
          ModelFallbackMiddleware(
              gemini_2_5_pro,
          ),
        ],
        tools=tools,
        system_prompt=prompt_v2,
        checkpointer=dynamic_checkpointer,
        store=dynamic_store  # <-- CRUCIAL FIX: Dynamic Store!
    )
