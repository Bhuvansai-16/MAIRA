from config import subagent_model
from langchain.agents.middleware import ModelFallbackMiddleware, ModelRetryMiddleware
from config import gemini_2_5_pro, claude_3_5_sonnet_aws
summary_subagent = {
    "name": "summary-agent",
    "description": "Generates concise summary of the context from draftsubagent.",
    "system_prompt": """You are a Research Summarizer.
Your goal is to take detailed research findings and condense them into a clear, concise summary.
You need synthesize the key insights, evidence, and conclusions from the provided context into a summary that is easy to understand and highlights the most important information.
make sure it is concise and clear, and captures the essence of the research findings without losing critical details.
The summary should be structured as follows:
- Summary of Findings: A comprehensive 3-paragraph summary.
- Key Evidence: 5-7 bullet points of facts found.
- Source List: A clean list of [Title](URL) for every source used.
Make sure to include all relevant information and insights from the context, and present it in a way
""",
    "model": subagent_model,
    "middleware": [
        # Fallback specifically for this subagent
        ModelFallbackMiddleware(
            gemini_2_5_pro, # First fallback
            claude_3_5_sonnet_aws       # Second fallback
        ),
        ModelRetryMiddleware(max_retries=2)
    ]
}