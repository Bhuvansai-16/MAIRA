---
name: github-agent
description: >
  GitHub Repository Analysis subagent that interacts with any public GitHub repository via dynamic API tools.
  Provides comprehensive repository analysis including project overview, file structure, tech stack detection,
  code reading, directory listing, code search, and issue tracking. Uses GitHub App authentication with
  JWT tokens. Invoked as a pre-processing step whenever a GitHub URL is detected in user messages, before
  the main workflow proceeds.
license: MIT
compatibility: Requires GitHub App credentials (App ID, private key) or personal access token
metadata:
  author: MAIRA Team
  version: "1.0"
  allowed-tools: analyze_github_repo, get_github_file_content, get_github_directory, search_github_code, get_github_issues
---

# github-agent — GitHub Repository Analyst

## Overview

The `github-agent` is a specialized subagent for analyzing any public GitHub repository from its URL.
It provides deep repository insights including project overview, file structure, tech stack, code reading,
and issue tracking. It uses GitHub's REST API with GitHub App authentication (JWT-based).

**Dictionary-Based SubAgent Definition:**
```python
github_subagent = {
    "name": "github-agent",
    "description": "Analyzes GitHub repositories from URLs. Provides project overview, key files, tech stack, code structure, and issue tracking.",
    "system_prompt": "...",  # Full prompt in github_subagent.py
    "tools": [
        analyze_github_repo,
        get_github_file_content,
        get_github_directory,
        search_github_code,
        get_github_issues,
    ],
    "model": subagent_model  # Default: gemini_3_flash
}
```

---

## When the Main Agent Should Invoke This Subagent

- **Pre-Workflow Step** — ALWAYS invoked **BEFORE** any tier workflow when a GitHub URL is detected
- Called when the user message contains `github.com/owner/repo` or `https://github.com/...`
- The gathered context is stored and used by subsequent workflow steps

**Invocation Pattern:**
```python
task(name="github-agent", task="Analyze the repository at https://github.com/owner/repo. Provide: 1) Project overview, 2) Key files and their purposes, 3) Tech stack used, 4) Code structure summary")
```

---

## Tools

| Tool | Purpose | Details |
|------|---------|---------|
| `analyze_github_repo` | Comprehensive repo overview | Description, language, stars, forks, recent activity, top-level structure |
| `get_github_file_content` | Read a specific file | Auto-skips binary files and files >50KB |
| `get_github_directory` | List directory contents | File types and sizes for any directory |
| `search_github_code` | Search code within repo | Requires authentication; falls back to file reading |
| `get_github_issues` | List repository issues | Open/closed/all, with labels and status |

---

## Capabilities

### Repository Analysis
- Full project overview with description, stars, forks
- Primary language and all languages used
- Recent activity (latest commits)
- License information
- Top-level file structure

### Code Reading
- Read any file in the repository
- Automatic binary file detection and skipping
- Size limit protection (>50KB files skipped to prevent context overflow)
- Support for navigating subdirectories

### Issue Tracking
- List open, closed, or all issues
- Issue labels and status
- Configurable limit (default 10, max 30)

### Code Search
- Search for functions, variables, patterns within the repository
- Note: Requires authentication; may fall back to manual file reading

---

## Authentication

The agent uses **GitHub App authentication** with:
1. **GitHub App ID** from environment variable
2. **Private key** from PEM file or environment variable
3. **JWT token generation** for API authentication
4. Automatic installation token retrieval for repository access

**Fallback:** If GitHub App auth fails, the agent can still access public repositories
using unauthenticated API requests (with lower rate limits).

---

## URL Parsing

The agent accepts GitHub URLs in multiple formats:
```
https://github.com/owner/repo
github.com/owner/repo
owner/repo
https://github.com/owner/repo/tree/main/src
```

All formats are parsed to extract the owner and repository name.

---

## Output Format

The agent provides structured analysis:

```markdown
## Repository Overview
- **Name:** owner/repo
- **Description:** [description]
- **Primary Language:** [language]
- **Stars:** [count] | **Forks:** [count]
- **License:** [license]

## File Structure
[Top-level directory listing]

## Key Files
- `README.md` — Project documentation
- `src/main.py` — Main application entrypoint
- ...

## Tech Stack
- Language: Python
- Framework: FastAPI
- Database: PostgreSQL
- ...

## Recent Activity
- [Latest commits summary]
```

---

## Integration with Main Agent Workflows

### GitHub + CHAT Mode
- Agent provides repo context
- Main agent uses context to answer questions directly
- References specific files when relevant

### GitHub + DEEP_RESEARCH Mode
- Agent provides repo context
- Main agent includes repo analysis in planning phase
- `websearch-agent` and `academic-paper-agent` research best practices for the repo's tech stack
- `draft-subagent` combines repo context with research findings
- `report-subagent` generates report with repo-specific recommendations

### GitHub + LITERATURE_SURVEY Mode
- Agent provides repo context
- `literature-survey-agent` focuses search on the repo's domain/technology
- Research connects findings to specific aspects of the codebase

---

## Safety Considerations

The agent only uses **read-only** operations:
- ✅ Get Issues, Read File, Search Code, List Branches, Get Files from Directory, Overview of Files
- ❌ Never creates, updates, or deletes repository content
- ❌ Never pushes commits or creates pull requests

**Safe Tool Names:**
```python
SAFE_TOOL_NAMES = [
    "Get Issues",
    "Get Issue",
    "Read File",
    "Search code",
    "List branches in this repository",
    "Get files from a directory",
    "Overview of existing files in Main branch",
]
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid GitHub URL | Returns parsing error with guidance |
| Private repository | Returns access denied error |
| File >50KB | Auto-skips with size warning |
| Binary file | Auto-skips with type warning |
| API rate limit | Reports remaining requests and retry timing |
| Authentication failure | Falls back to unauthenticated access |
