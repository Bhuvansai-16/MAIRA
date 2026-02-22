from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

# Initialize model
#latex_model = ChatGroq(model="llama-3.1-8b-instant", temperature=0.7)
latex_model = ChatGroq(model="openai/gpt-oss-120b", temperature=0.7)
# Create prompt for LaTeX generation
latex_prompt = ChatPromptTemplate.from_template(
    """Generate a comprehensive, academic LaTeX-formatted document about: {topic}

CRITICAL STRUCTURE REQUIREMENTS:
- DO NOT include \\documentclass, \\usepackage, \\begin{{document}}, or \\end{{document}}.
- DO NOT use \\maketitle. 
- Output ONLY the raw document body (sections, content, tables, equations). 
- The backend system will automatically handle the LaTeX preamble, title page, date, and margins.
- Start directly with your first \\section{{Introduction}} or abstract.

TABLE FORMATTING:
- Use tabularx for responsive tables: \\begin{{tabularx}}{{\\textwidth}}{{l X X X}} for flexible columns
- Always use booktabs: \\toprule, \\midrule, \\bottomrule
- Wrap tables in \\begin{{table}}[H] with \\centering
- Add \\caption and \\label for each table
- Use \\renewcommand{{\\arraystretch}}{{1.3}} before tables for better row spacing

CONTENT RULES:
- Include sections and subsections with descriptive headings
- DO NOT include any subtitle, author name, or agent attribution in the document
- DO NOT include any images or figures in the document
- Use proper text alignment and paragraph spacing
- Include itemize/enumerate lists where appropriate
- Add meaningful content (3-4 pages worth)
- Use proper LaTeX formatting for emphasis (\\textbf{{}}, \\textit{{}}, \\emph{{}})
- Include a bibliography or references section if applicable

Return ONLY the LaTeX code. No markdown code blocks, no explanations."""
)

# Create chain
latex_chain = latex_prompt | latex_model
