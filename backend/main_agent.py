from deepagents import create_deep_agent
from websearch_subagent import websearch_subagent
from paper_agent import academic_paper_subagent
from draft_agent import draft_subagent
from report_agent import report_subagent
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import MemorySaver
from config import model
import os
from dotenv import load_dotenv
load_dotenv()

research_prompt = """You are a thorough research agent. Your job is to:
1. Break down research questions into specific sub-tasks
2. Use the websearch-agent subagent to search the internet and gather web information
3. Use the academic-paper-agent subagent to retrieve relevant academic papers from arXiv
4. Complete ALL planned tasks before providing your final answer
5. Synthesize all findings into a comprehensive response
6. Use the draft-subagent subagent to create a structured research draft
7. Use the report-subagent subagent to convert the research draft into a professional report

IMPORTANT/WARNING: You must execute each planned task using the appropriate subagent, not just plan them.
After completing all research tasks, provide a final synthesized answer to the user.
Do NOT return until you have completed all research and can provide a full answer.
"""

subagents = [websearch_subagent, academic_paper_subagent, draft_subagent, report_subagent]
agent = create_deep_agent(
    subagents=subagents,
    model=model,
    system_prompt=research_prompt,
    store=InMemoryStore(),
    checkpointer=MemorySaver(),
)