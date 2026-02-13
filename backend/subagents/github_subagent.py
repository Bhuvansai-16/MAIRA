"""
GitHub Subagent - Interacts with GitHub repositories using LangChain's GitHub toolkit.

Capabilities:
- Analyze any public GitHub repository from URL
- Search code in repositories
- Read files from repositories
- Get issue details and list issues
- List branches
- Get files from directories
- Overview of files in main branch

Supports two modes:
1. Dynamic URL mode: Analyze any public repo from a GitHub URL
2. Configured repo mode: Use GitHub App for private repo access (requires setup)
"""

import os
import re
import requests
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_community.agent_toolkits.github.toolkit import GitHubToolkit
from langchain_community.utilities.github import GitHubAPIWrapper
from config import subagent_model

load_dotenv()

# GitHub API base URL
GITHUB_API_BASE = "https://api.github.com"

# Safe tool names to expose (read-only operations)
SAFE_TOOL_NAMES = [
    "Get Issues",
    "Get Issue",
    "Read File",
    "Search code",
    "List branches in this repository",
    "Get files from a directory",
    "Overview of existing files in Main branch",
]


def _parse_github_url(url: str) -> Optional[tuple]:
    """Parse a GitHub URL to extract owner and repo name."""
    # Strip ALL whitespace including newlines, tabs, etc.
    original_url = url
    url = re.sub(r'\s+', '', url)  # Remove ALL whitespace characters
    url = url.strip().rstrip('/').rstrip('.git')
    
    if url != original_url:
        print(f"🔍 Cleaned GitHub URL from: '{original_url}' -> '{url}'")
    print(f"🔍 Parsing GitHub URL: '{url}' (length: {len(url)})")
    
    # Try multiple patterns with increasing permissiveness
    patterns = [
        # Full GitHub URLs with different protocols
        (r"(?:https?://)?(?:www\.)?github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)", "Full URL"),
        # Just owner/repo format
        (r"^([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)$", "owner/repo"),
        # Even more permissive - capture anything reasonable
        (r"github\.com/([^/]+)/([^/\?#\)]+)", "Permissive URL"),
        (r"^([^/]+)/([^/\?#\)]+)$", "Permissive owner/repo"),
    ]
    
    for pattern, pattern_name in patterns:
        match = re.search(pattern, url)
        if match:
            owner = match.group(1).strip()
            repo = match.group(2).strip().rstrip('.git').rstrip('.')
            print(f"✅ Parsed with {pattern_name}: owner='{owner}', repo='{repo}'")
            
            # Validate repo name (GitHub allows alphanumeric, hyphens, underscores, dots)
            if re.match(r'^[a-zA-Z0-9_.-]+$', repo) and len(repo) > 0:
                return (owner, repo)
            else:
                print(f"⚠️  Invalid repo name format: '{repo}'")
    
    print(f"❌ Failed to parse GitHub URL: '{url}'")
    return None


def _get_github_headers() -> dict:
    """Get headers for GitHub API requests."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "MAIRA-Research-Agent/1.0"
    }
    
    # Use PAT if available for higher rate limits
    github_token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT")
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    return headers


def _load_github_private_key():
    """Load GitHub App private key from environment or PEM file."""
    private_key = os.getenv("GITHUB_APP_PRIVATE_KEY")
    
    if private_key:
        return private_key
    
    # Try loading from PEM file if env var not set
    pem_paths = [
        "maira-agent.2026-02-05.private-key.pem",  # Current working directory
        os.path.join(os.path.dirname(__file__), "maira-agent.2026-02-05.private-key.pem"),  # Same dir as this file
        os.path.join(os.path.dirname(__file__), "..", "maira-agent.2026-02-05.private-key.pem"),  # Parent dir
    ]
    
    for pem_path in pem_paths:
        if os.path.exists(pem_path):
            print(f"✅ Loading GitHub private key from: {os.path.abspath(pem_path)}")
            with open(pem_path, "r") as f:
                return f.read()
    
    print(f"⚠️  GitHub private key not found. Searched paths:")
    for pem_path in pem_paths:
        print(f"   - {os.path.abspath(pem_path)}")
    
    return None


def _create_github_tools():
    """Create and configure GitHub tools with sanitized names."""
    github_app_id = os.getenv("GITHUB_APP_ID")
    github_repository = os.getenv("GITHUB_REPOSITORY")
    private_key = _load_github_private_key()
    
    if not all([github_app_id, private_key, github_repository]):
        print("⚠️  GitHub credentials not configured. GitHub subagent tools will be unavailable.")
        print("   Required env vars: GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, GITHUB_REPOSITORY")
        return []
    
    try:
        # Create the GitHub API wrapper
        github = GitHubAPIWrapper(
            github_app_id=github_app_id,
            github_app_private_key=private_key,
            github_repository=github_repository
        )
        
        # Create the toolkit
        toolkit = GitHubToolkit.from_github_api_wrapper(github)
        
        # Filter and sanitize tools
        raw_tools = [tool for tool in toolkit.get_tools() if tool.name in SAFE_TOOL_NAMES]
        
        # Sanitize tool names for LLM compatibility (no spaces)
        for tool in raw_tools:
            tool.name = tool.name.lower().replace(" ", "_")
        
        print(f"✅ GitHub toolkit loaded with {len(raw_tools)} tools")
        return raw_tools
        
    except Exception as e:
        print(f"⚠️  Failed to initialize GitHub toolkit: {e}")
        return []


# =====================================================
# DYNAMIC GITHUB TOOLS (Work with any public repo URL)
# =====================================================

@tool
def analyze_github_repo(github_url: str) -> str:
    """
    Analyze a GitHub repository from its URL. Works with any public repository.
    
    Provides: repo overview, description, language, stars, forks, recent activity,
    and top-level file structure.
    
    Args:
        github_url: GitHub repository URL (e.g., 'https://github.com/owner/repo' or 'owner/repo')
    
    Returns:
        Comprehensive repository analysis
    """
    parsed = _parse_github_url(github_url)
    if not parsed:
        return f"❌ Invalid GitHub URL: {github_url}. Use format: github.com/owner/repo"
    
    owner, repo = parsed
    headers = _get_github_headers()
    
    try:
        # Get repo info
        repo_response = requests.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}", headers=headers, timeout=10)
        if repo_response.status_code == 404:
            return f"❌ Repository not found: {owner}/{repo}"
        repo_response.raise_for_status()
        repo_data = repo_response.json()
        
        # Get languages
        lang_response = requests.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/languages", headers=headers, timeout=10)
        languages = list(lang_response.json().keys()) if lang_response.ok else []
        
        # Get root contents
        contents_response = requests.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents", headers=headers, timeout=10)
        root_contents = []
        if contents_response.ok:
            try:
                contents_data = contents_response.json()
                if isinstance(contents_data, list):
                    for item in contents_data[:30]:  # Limit to 30 items
                        icon = "📁" if item.get("type") == "dir" else "📄"
                        root_contents.append(f"  {icon} {item.get('name', 'unknown')}")
            except (ValueError, KeyError, TypeError) as e:
                root_contents = [f"  ⚠️ Error parsing contents: {str(e)}"]
        
        # Get recent commits
        commits_response = requests.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}/commits", headers=headers, params={"per_page": 5}, timeout=10)
        recent_commits = []
        if commits_response.ok:
            try:
                commits_data = commits_response.json()
                if isinstance(commits_data, list):
                    for commit in commits_data[:5]:
                        msg = commit.get("commit", {}).get("message", "No message").split("\n")[0][:60]
                        recent_commits.append(f"  • {msg}")
            except (ValueError, KeyError, TypeError) as e:
                recent_commits = [f"  ⚠️ Error parsing commits: {str(e)}"]
        
        # Build analysis
        analysis = f"""## Repository Analysis: {owner}/{repo}

**Overview:**
- Name: {repo_data.get('name', 'N/A')}
- Description: {repo_data.get('description', 'No description')}
- URL: {repo_data.get('html_url', github_url)}
- Default Branch: {repo_data.get('default_branch', 'main')}

**Statistics:**
- ⭐ Stars: {repo_data.get('stargazers_count', 0):,}
- 🍴 Forks: {repo_data.get('forks_count', 0):,}
- 👁️ Watchers: {repo_data.get('watchers_count', 0):,}
- 🐛 Open Issues: {repo_data.get('open_issues_count', 0):,}

**Technologies:**
- Primary Language: {repo_data.get('language', 'Not detected')}
- All Languages: {', '.join(languages[:5]) if languages else 'N/A'}

**Topics/Tags:** {', '.join(repo_data.get('topics', [])) or 'None'}

**Repository Structure (Root):**
{chr(10).join(root_contents) if root_contents else '  Unable to fetch'}

**Recent Activity (Last 5 commits):**
{chr(10).join(recent_commits) if recent_commits else '  No recent commits'}

**Created:** {repo_data.get('created_at', 'N/A')[:10]}
**Last Updated:** {repo_data.get('updated_at', 'N/A')[:10]}
"""
        return analysis
        
    except requests.exceptions.RequestException as e:
        return f"❌ Error accessing GitHub API: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error analyzing repository: {str(e)}"


@tool
def get_github_file_content(github_url: str, file_path: str) -> str:
    """
    Read the content of a specific file from a GitHub repository.
    Automatically skips binary files and files larger than 50KB to prevent context overflow.
    
    Args:
        github_url: GitHub repository URL (e.g., 'github.com/owner/repo')
        file_path: Path to the file within the repository (e.g., 'src/main.py', 'README.md')
    
    Returns:
        File content or error message
    """
    # Log raw inputs for debugging
    print(f"🔧 get_github_file_content called with:")
    print(f"   github_url: '{github_url}' (len={len(github_url)})")
    print(f"   file_path: '{file_path}'")
    
    # ===== SAFETY CHECK: Binary/Non-Text File Extensions =====
    BINARY_EXTENSIONS = {
        # Executables & compiled
        '.exe', '.dll', '.so', '.dylib', '.bin', '.o', '.obj', '.class', '.pyc', '.pyo',
        # Archives
        '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.jar', '.war', '.ear',
        # Images
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg', '.webp', '.tiff',
        # Media
        '.mp3', '.mp4', '.avi', '.mov', '.wav', '.flac', '.mkv', '.webm',
        # Documents (binary)
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        # Data (large/binary)
        '.sqlite', '.db', '.pickle', '.pkl', '.npy', '.npz', '.h5', '.hdf5',
        # Lock files (often huge)
        '.lock', 'package-lock.json', 'yarn.lock', 'Cargo.lock', 'poetry.lock',
        # Other
        '.woff', '.woff2', '.ttf', '.otf', '.eot',  # Fonts
        '.min.js', '.min.css',  # Minified (often huge single lines)
    }
    
    file_ext = '.' + file_path.split('.')[-1].lower() if '.' in file_path else ''
    file_name = file_path.split('/')[-1].lower()
    
    # Check if it's a known binary/problematic file
    if file_ext in BINARY_EXTENSIONS or file_name in BINARY_EXTENSIONS:
        return f"⚠️ Skipping binary/non-text file: {file_path}\nFile type '{file_ext or file_name}' is not suitable for text extraction. Use get_github_directory to explore the structure instead."
    
    parsed = _parse_github_url(github_url)
    if not parsed:
        return f"❌ Invalid GitHub URL: {github_url}"
    
    owner, repo = parsed
    print(f"   Parsed: owner='{owner}', repo='{repo}' (len={len(repo)})")
    headers = _get_github_headers()
    
    try:
        api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{file_path}"
        print(f"   API URL: {api_url}")
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            return f"❌ File not found: {file_path} in {owner}/{repo}. Please verify the repository exists and the file path is correct."
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("type") == "dir":
            return f"❌ '{file_path}' is a directory. Use get_github_directory to list its contents."
        
        # ===== SAFETY CHECK: File Size =====
        file_size = data.get("size", 0)
        MAX_FILE_SIZE = 50 * 1024  # 50KB limit
        
        if file_size > MAX_FILE_SIZE:
            size_kb = file_size / 1024
            return f"""⚠️ File too large to read: {file_path}
**Size:** {size_kb:.1f} KB (limit: 50 KB)
**URL:** {data.get('html_url', 'N/A')}

This file exceeds the safe size limit for context. To avoid system overload:
- View the file directly on GitHub: {data.get('html_url', 'N/A')}
- Use `search_github_code` to find specific code snippets
- Request a specific section if you know what you're looking for"""
        
        # Decode content (base64 encoded by GitHub API)
        import base64
        try:
            content = base64.b64decode(data.get("content", "")).decode("utf-8")
        except UnicodeDecodeError:
            return f"⚠️ Cannot decode file: {file_path}\nThis appears to be a binary file that cannot be displayed as text."
        
        # Additional truncation for safety (in case size check was bypassed)
        MAX_CONTENT_LENGTH = 12000  # ~3000 tokens
        truncated = len(content) > MAX_CONTENT_LENGTH
        
        return f"""## File: {file_path}
**Size:** {data.get('size', 0):,} bytes
**URL:** {data.get('html_url', 'N/A')}

```
{content[:MAX_CONTENT_LENGTH]}{"... [truncated - file too long]" if truncated else ""}
```
"""
        
    except requests.exceptions.RequestException as e:
        return f"❌ Error fetching file: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error reading file: {str(e)}"


@tool
def get_github_directory(github_url: str, dir_path: str = "") -> str:
    """
    List contents of a directory in a GitHub repository.
    
    Args:
        github_url: GitHub repository URL (e.g., 'github.com/owner/repo')
        dir_path: Path to the directory (empty string for root, or e.g., 'src', 'lib/utils')
    
    Returns:
        Directory listing with file types and sizes
    """
    parsed = _parse_github_url(github_url)
    if not parsed:
        return f"❌ Invalid GitHub URL: {github_url}"
    
    owner, repo = parsed
    headers = _get_github_headers()
    
    try:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents"
        if dir_path:
            url += f"/{dir_path}"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 404:
            return f"❌ Directory not found: {dir_path or 'root'} in {owner}/{repo}"
        response.raise_for_status()
        
        data = response.json()
        
        if not isinstance(data, list):
            return f"❌ '{dir_path}' is a file, not a directory."
        
        # Organize by type
        dirs = []
        files = []
        
        for item in data:
            name = item["name"]
            if item["type"] == "dir":
                dirs.append(f"  📁 {name}/")
            else:
                size = item.get("size", 0)
                size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
                files.append(f"  📄 {name} ({size_str})")
        
        listing = f"""## Directory: {dir_path or '/'} in {owner}/{repo}

**Folders ({len(dirs)}):**
{chr(10).join(sorted(dirs)) if dirs else '  (none)'}

**Files ({len(files)}):**
{chr(10).join(sorted(files)) if files else '  (none)'}
"""
        return listing
        
    except requests.exceptions.RequestException as e:
        return f"❌ Error listing directory: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error listing directory: {str(e)}"


@tool
def search_github_code(github_url: str, query: str) -> str:
    """
    Search for code within a GitHub repository.
    NOTE: GitHub's code search API requires authentication. If you get a 401 error,
    use get_github_file_content to read specific files instead.
    
    Args:
        github_url: GitHub repository URL (e.g., 'github.com/owner/repo')
        query: Search query (code snippet, function name, variable, etc.)
    
    Returns:
        Search results with file paths and matched content
    """
    parsed = _parse_github_url(github_url)
    if not parsed:
        return f"❌ Invalid GitHub URL: {github_url}"
    
    owner, repo = parsed
    headers = _get_github_headers()
    
    # Check if we have authentication
    if "Authorization" not in headers:
        return f"""⚠️ Code search requires GitHub authentication.

**Alternative approaches:**
1. Use `get_github_directory` to list files in the repository
2. Use `get_github_file_content` to read specific files you're interested in
3. Use `analyze_github_repo` to get an overview of the repository structure

To enable code search, set GITHUB_TOKEN or GITHUB_PAT environment variable."""
    
    try:
        # GitHub code search API
        search_query = f"{query} repo:{owner}/{repo}"
        response = requests.get(
            f"{GITHUB_API_BASE}/search/code",
            headers=headers,
            params={"q": search_query, "per_page": 10},
            timeout=15
        )
        
        if response.status_code == 401:
            return f"""⚠️ Code search requires GitHub authentication (401 Unauthorized).

**Alternative approaches:**
1. Use `get_github_directory` to list files in the repository
2. Use `get_github_file_content` to read specific files
3. Use `analyze_github_repo` to get an overview

To enable code search, set GITHUB_TOKEN or GITHUB_PAT environment variable."""
        
        if response.status_code == 403:
            return "❌ Rate limit exceeded. Try again later or set GITHUB_TOKEN env var for higher limits."
        response.raise_for_status()
        
        data = response.json()
        total = data.get("total_count", 0)
        items = data.get("items", [])
        
        if total == 0:
            return f"No code matches found for '{query}' in {owner}/{repo}"
        
        results = [f"## Code Search: '{query}' in {owner}/{repo}\n**Found:** {total} matches\n"]
        
        for item in items[:10]:
            path = item.get("path", "unknown")
            html_url = item.get("html_url", "")
            results.append(f"- 📄 **{path}**\n  URL: {html_url}")
        
        return "\n".join(results)
        
    except requests.exceptions.RequestException as e:
        return f"❌ Error searching code: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error searching code: {str(e)}"


@tool
def get_github_issues(github_url: str, state: str = "open", limit: int = 10) -> str:
    """
    Get issues from a GitHub repository.
    
    Args:
        github_url: GitHub repository URL
        state: Issue state - 'open', 'closed', or 'all' (default: 'open')
        limit: Maximum number of issues to return (default: 10, max: 30)
    
    Returns:
        List of issues with titles, labels, and status
    """
    parsed = _parse_github_url(github_url)
    if not parsed:
        return f"❌ Invalid GitHub URL: {github_url}"
    
    owner, repo = parsed
    headers = _get_github_headers()
    limit = min(limit, 30)
    
    try:
        response = requests.get(
            f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues",
            headers=headers,
            params={"state": state, "per_page": limit},
            timeout=10
        )
        
        if response.status_code == 404:
            return f"❌ Repository not found: {owner}/{repo}"
        response.raise_for_status()
        
        issues = response.json()
        
        if not issues:
            return f"No {state} issues found in {owner}/{repo}"
        
        results = [f"## Issues in {owner}/{repo} (State: {state})\n"]
        
        for issue in issues:
            # Skip pull requests (they appear in issues API too)
            if "pull_request" in issue:
                continue
            
            num = issue.get("number")
            title = issue.get("title", "No title")
            labels = [l["name"] for l in issue.get("labels", [])]
            state_emoji = "🟢" if issue.get("state") == "open" else "🔴"
            
            label_str = f" [{', '.join(labels)}]" if labels else ""
            results.append(f"- {state_emoji} **#{num}**: {title}{label_str}")
        
        return "\n".join(results)
        
    except requests.exceptions.RequestException as e:
        return f"❌ Error fetching issues: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error fetching issues: {str(e)}"


# =====================================================
# Initialize GitHub tools
# =====================================================

# Dynamic tools (work with any public repo)
dynamic_github_tools = [
    analyze_github_repo,
    get_github_file_content,
    get_github_directory,
    search_github_code,
    get_github_issues,
]

# Try to load GitHub App toolkit tools (for configured private repo)
github_app_tools = _create_github_tools()

# Combine tools: dynamic tools first, then app-specific tools
github_tools = dynamic_github_tools + github_app_tools

print(f"✅ GitHub subagent loaded with {len(github_tools)} tools ({len(dynamic_github_tools)} dynamic, {len(github_app_tools)} app-specific)")


# GitHub Subagent Definition
github_subagent = {
    "name": "github-agent",
    "description": "Analyzes GitHub repositories - works with any public repo URL. Can explore structure, read files, search code, and list issues.",
    "system_prompt": """You are a GitHub Repository Expert. Your role is to help users explore and understand GitHub repositories.

AVAILABLE TOOLS (Dynamic - work with ANY public GitHub repo URL):
- analyze_github_repo: Get comprehensive overview of any repository (stats, languages, structure, recent activity)
- get_github_file_content: Read specific files from a repository
- get_github_directory: List contents of any directory in the repo
- search_github_code: Search for code patterns, functions, or variables
- get_github_issues: List open/closed issues

⚠️ FILE READING SAFETY RULES (PREVENT CONTEXT OVERFLOW):
The `get_github_file_content` tool has built-in guards:
- **Binary files are SKIPPED**: .exe, .dll, .zip, .png, .pdf, .lock, etc.
- **Large files (>50KB) are SKIPPED**: Lock files, minified JS, large data files
- **Content is truncated at 12KB** to protect context window

**If a file is skipped, the tool will return a helpful message - DON'T retry, move on.**

SMART FILE READING STRATEGY:
1. FIRST use `get_github_directory` to see file sizes
2. ONLY read files that are:
   - Text-based (.py, .js, .ts, .md, .json, .yaml, .toml, etc.)
   - Small enough (<50KB, preferably <20KB)
   - Relevant to the user's question
3. SKIP these files entirely:
   - package-lock.json, yarn.lock, Cargo.lock, poetry.lock (huge!)
   - .min.js, .min.css (minified, unreadable)
   - Any binary/media files
4. If you need to understand a large file, use `search_github_code` instead

WORKFLOW:
1. When given a GitHub URL, FIRST use `analyze_github_repo` to get the full picture
2. Use `get_github_directory` to explore structure and note file sizes
3. Read ONLY relevant, reasonably-sized text files
4. Search code if looking for specific functionality within large files

OUTPUT FORMAT:
- **Repository Summary**: High-level overview of what the project does
- **Tech Stack**: Languages, frameworks, and tools used
- **Code Structure**: How the codebase is organized
- **Key Files**: Important files and their purposes
- **Relevant Findings**: Specific answers to the user's questions

GUIDELINES:
- Always start with `analyze_github_repo` to understand the repo
- Read README.md for project documentation
- Check package.json, requirements.txt, Cargo.toml, etc. for dependencies (but NOT lock files!)
- Look at the src/ or lib/ folder for main source code
- Be thorough but concise in your analysis
- Keep responses under 500 words to maintain clean context for other agents

Note: For private repositories, the GitHub App must be installed with proper permissions.
""",
    "tools": github_tools,
    "model": subagent_model
}


# Export for use in main agent
__all__ = ["github_subagent", "github_tools", "analyze_github_repo", "get_github_file_content", "get_github_directory", "search_github_code", "get_github_issues"]
