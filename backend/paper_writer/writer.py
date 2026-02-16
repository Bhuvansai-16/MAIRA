"""
Paper Writer Agent
AI assistant for modifying LaTeX templates based on user instructions.
Returns updated LaTeX code with a summary of changes made.
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv
import json
import re

load_dotenv()

# Use a fast model for interactive editing
writer_model = ChatGoogleGenerativeAI(
    model="models/gemini-2.5-flash",
    temperature=0.2,
    max_retries=2
)

WRITER_SYSTEM_PROMPT = """You are an expert LaTeX paper writing assistant integrated into a research paper editor.

**YOUR ROLE:**
You help users modify their LaTeX documents based on their instructions. You can:
- Add new sections, subsections, or content
- Modify existing text, titles, authors, or formatting
- Fix LaTeX errors and suggest improvements
- Add tables, figures, equations, or bibliographic entries
- Restructure the document organization
- Apply formatting changes (fonts, spacing, margins, etc.)

**RESPONSE FORMAT:**
You MUST respond in EXACTLY this JSON format (no markdown code fences):
{
    "updated_latex": "THE COMPLETE UPDATED LATEX CODE HERE",
    "changes_summary": "A brief bullet-point summary of what was changed",
    "change_type": "content|structure|formatting|fix"
}

**CRITICAL RULES:**
1. ALWAYS return the COMPLETE LaTeX document in "updated_latex" — never partial snippets
2. Only modify what the user asked for; preserve everything else exactly
3. Keep the LaTeX valid and compilable
4. The "changes_summary" should be human-readable, describing each change made
5. If the user asks a question without requesting changes, set "updated_latex" to null and answer in "changes_summary"
6. "change_type" indicates the primary type: "content" for text changes, "structure" for adding/removing sections, "formatting" for style changes, "fix" for error corrections
7. Do NOT wrap your response in ```json``` or any markdown — return raw JSON only
"""


def process_writer_request(message: str, paper_content: str = None, chat_history: list = None) -> dict:
    """
    Process a user request to modify their LaTeX paper.
    
    Args:
        message: User's instruction/question
        paper_content: Current LaTeX content of the active file
        chat_history: Previous messages for context continuity
    
    Returns:
        dict with 'response' (text summary), 'updated_latex' (new code or None), 
        'change_type' (str), and 'success' (bool)
    """
    messages = [SystemMessage(content=WRITER_SYSTEM_PROMPT)]
    
    # Add chat history if available
    if chat_history:
        for msg in chat_history[-6:]:  # Keep last 6 messages for context
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg["text"]))
            else:
                messages.append(SystemMessage(content=f"[Previous AI response]: {msg['text']}"))
    
    # Build the current request
    user_content = f"**User Instruction:** {message}"
    if paper_content:
        user_content += f"\n\n**Current LaTeX Document:**\n```latex\n{paper_content}\n```"
    else:
        user_content += "\n\n(No document is currently open)"
    
    messages.append(HumanMessage(content=user_content))
    
    try:
        response = writer_model.invoke(messages)
        response_text = response.content.strip()
        
        # Clean up response — remove markdown fences if present
        if response_text.startswith("```"):
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        # Parse JSON response
        try:
            parsed = json.loads(response_text)
            return {
                "success": True,
                "response": parsed.get("changes_summary", "Changes applied."),
                "updated_latex": parsed.get("updated_latex"),
                "change_type": parsed.get("change_type", "content")
            }
        except json.JSONDecodeError:
            # If model didn't return valid JSON, treat as a text response
            return {
                "success": True,
                "response": response_text,
                "updated_latex": None,
                "change_type": "info"
            }
    except Exception as e:
        return {
            "success": False,
            "response": f"Sorry, I encountered an error: {str(e)}",
            "updated_latex": None,
            "change_type": "error"
        }