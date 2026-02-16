---
name: summary-agent
description: >
  Research Summarizer subagent that generates concise, structured summaries from draft-subagent output.
  Distills detailed research findings into a clear format with a 3-paragraph findings summary, 5–7 key
  evidence bullet points, and a clean source list. No tools — relies entirely on reasoning. Called after
  the draft is verified and before the report-subagent generates the final document.
license: MIT
compatibility: No external tool dependencies. Receives verified draft output from the pipeline.
metadata:
  author: MAIRA Team
  version: "1.0"
  allowed-tools: none
---

# summary-agent — Research Summarizer

## Overview

The `summary-agent` is a lightweight, tool-free subagent that takes detailed research findings (typically
from the `draft-subagent`) and condenses them into a clear, structured summary. This summary is included
in the main agent's final response to give users a quick overview before the downloadable report.

**Dictionary-Based SubAgent Definition:**
```python
summary_subagent = {
    "name": "summary-agent",
    "description": "Generates concise summary of the context from draftsubagent.",
    "system_prompt": "...",  # Full prompt below
    "model": subagent_model  # Default: gemini_3_flash
}
```

---

## When the Main Agent Should Invoke This Subagent

- **Tier 3 (Deep Research)** — Step 5 (Summary), after the draft passes verification
- Called AFTER `deep-reasoning-agent` returns STATUS: VALID (or after max revisions)
- Called BEFORE `report-subagent` generates the final document

**Invocation Pattern:**
```python
task(name="summary-agent", task="Summarize the following verified research draft on [topic]: [draft content]")
```

---

## Tools

None. The `summary-agent` is a pure reasoning agent with no tool access.

---

## Output Format

The summary follows a strict three-part structure:

```markdown
## Summary of Findings
A comprehensive 3-paragraph summary that captures the essence of the research
findings without losing critical details.

Paragraph 1: [Overview of the main topic and scope of the research]

Paragraph 2: [Key discoveries, methodologies, and significant results]

Paragraph 3: [Implications, limitations, and areas for further investigation]

## Key Evidence
- Fact 1: [Specific finding with attribution]
- Fact 2: [Statistical evidence or data point]
- Fact 3: [Important comparison or contrast]
- Fact 4: [Technical insight or methodology finding]
- Fact 5: [Trend or pattern identified]
- Fact 6: [Notable limitation or gap]
- Fact 7: [Future direction or recommendation]

## Source List
- [Title 1](URL1)
- [Title 2](URL2)
- [Title 3](URL3)
- ...
```

---

## Requirements

| Attribute | Specification |
|-----------|--------------|
| Summary length | 3 comprehensive paragraphs |
| Key Evidence | 5–7 bullet points |
| Source List | Clean `[Title](URL)` format for every source |
| Tone | Clear, concise, professional |
| Coverage | Must capture essence without losing critical details |

---

## Pipeline Position

```
websearch-agent + academic-paper-agent
         ↓
    draft-subagent (drafting)
         ↓
    deep-reasoning-agent (verification)
         ↓
    summary-agent ← YOU ARE HERE
         ↓
    report-subagent (document generation)
         ↓
    Main agent final response (summary + download marker)
```

The summary output is included in the main agent's final response **before** the download marker,
giving users a text overview of the research before they download the full report.

---

## Integration with Final Response

The main agent's final response structure:

```markdown
## Research Summary

[summary-agent output here — 3 paragraphs + key evidence + sources]

[DOWNLOAD_DOCX]{"filename": "...", "data": "..."} ← from report-subagent
```

---

## Key Principles

1. **Concise but complete** — Capture the essence, not the entirety
2. **Structured** — Follow the exact three-part format
3. **Source-attributed** — Every claim traced to a source
4. **Reader-friendly** — Written for the end user, not for other agents
5. **No meta-commentary** — Don't describe what you're doing, just do it
