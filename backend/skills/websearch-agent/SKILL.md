---
name: websearch-agent
description: >
  Deep Web Researcher subagent that conducts comprehensive web research using internet search and webpage
  content extraction. Returns condensed summaries (never raw dumps) with relevant images in Markdown format.
  Use this subagent for non-academic information gathering: news, blogs, official sites, industry reports,
  and visual content discovery. Critical context management rules prevent system crashes from oversized responses.
license: MIT
compatibility: Requires Tavily API key for internet_search and extract_webpage tools
metadata:
  author: MAIRA Team
  version: "1.0"
  allowed-tools: internet_search, extract_webpage
---

# websearch-agent — Deep Web Researcher

## Overview

The `websearch-agent` is a specialized subagent for finding high-quality, non-academic information from the web.
It conducts multi-query searches, extracts and condenses webpage content, and discovers relevant images —
all while maintaining strict output size limits to prevent context overflow in downstream agents.

**Dictionary-Based SubAgent Definition:**
```python
websearch_subagent = {
    "name": "websearch-agent",
    "description": "Conducts deep web research and extracts webpage content, returning condensed summaries (not raw dumps) with relevant images.",
    "system_prompt": "...",  # Full prompt below
    "tools": [internet_search, extract_webpage],
    "model": subagent_model  # Default: gemini_3_flash
}
```

---

## When the Main Agent Should Invoke This Subagent

- **Tier 3 (Deep Research)** — Discovery phase, called in parallel with `academic-paper-agent`
- **Any time** the main agent needs comprehensive web research beyond a simple `internet_search` call
- When the research requires multiple searches, webpage extraction, and synthesis

**Invocation Pattern:**
```python
task(name="websearch-agent", task="Research recent developments in quantum computing, focusing on error correction and practical applications.")
```

---

## Tools

| Tool | Purpose | Details |
|------|---------|---------|
| `internet_search` | Web search via Tavily API | Returns URLs, snippets, and images. Supports topics: general, news, finance |
| `extract_webpage` | Extract full content from a URL | Returns raw webpage text — MUST be condensed before output |

---

## Research Process

### Step 1: Query Decomposition
Break down the user's research goal into **3–5 specific search queries**.

### Step 2: Web Search
Use `internet_search` to find relevant URLs and images for each query.

### Step 3: Content Extraction
Use `extract_webpage` to retrieve full content from **top 3–5 URLs ONLY**.

### Step 4: Immediate Summarization (CRITICAL)
After each extraction, **immediately condense** the content into 3–5 bullet points:

```
[10,000 word raw content] →
"From [Source]:
 - Key fact 1
 - Key statistic 2
 - Important quote 3"
```

### Step 5: Synthesis
Combine all summarized findings into the final structured output.

---

## Context Management Rules (CRITICAL — Prevent System Crash)

⚠️ These rules are non-negotiable:

| Rule | Limit |
|------|-------|
| **NEVER** return raw HTML or full webpage dumps | Causes system failure |
| Total response size | Under **800 words / ~3000 tokens** |
| Per-webpage condensation | Extract only **300–500 most relevant words** from any page |
| Prioritization | Facts, statistics, quotes over filler text |

---

## Image Handling

The `internet_search` tool returns images in its response. The agent MUST:

1. **Review** returned images from each search
2. **Select** top 2–3 most relevant, high-quality images that:
   - Directly relate to the research topic
   - Come from reputable sources (avoid ads, low-res, or irrelevant images)
   - Add visual value (diagrams, charts, infographics, product images)
3. **Include** selected images using Markdown syntax:
   ```markdown
   ![Descriptive Caption](image_url)
   ```

**Example:**
```markdown
![Architecture diagram of multi-agent systems](https://example.com/diagram.png)
```

---

## Output Format (STRICT — MAX 800 WORDS TOTAL)

```markdown
## Summary of Findings
A comprehensive 2–3 paragraph summary (200–300 words).

## Key Evidence
- Fact 1 with source attribution
- Statistic 2 with context
- Finding 3 from [Source](URL)
- ...5–7 bullet points total (100–150 words)

## Relevant Images
![Caption 1](url1)
![Caption 2](url2)
![Caption 3](url3)

## Source List
- [Title 1](URL1)
- [Title 2](URL2)
- ...
```

---

## Do's and Don'ts

### ✅ DO:
- Condense aggressively
- Prioritize quality over quantity
- Keep context clean for downstream agents (draft-subagent, deep-reasoning-agent)
- Include images with descriptive captions
- Attribute all facts to sources

### ❌ DO NOT:
- Return full webpage text
- Include more than 800 words total
- Skip the summarization step
- Include low-quality or irrelevant images
- Return raw HTML

---

## Downstream Integration

The output from `websearch-agent` feeds into:
1. **`draft-subagent`** — Synthesizes web findings with academic papers into a draft
2. **`deep-reasoning-agent`** — Cross-references web sources during fact-checking
3. **Main agent** — May use findings directly for Tier 2 responses

The websearch-agent's images (as `![caption](url)` Markdown) are preserved through the draft and report pipeline,
ultimately being embedded in the final PDF/DOCX output.
