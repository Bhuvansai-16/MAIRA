from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

# Initialize model
#latex_model = ChatGroq(model="llama-3.1-8b-instant", temperature=0.7)
latex_model = ChatGroq(model="openai/gpt-oss-120b", temperature=0.7)
# Create prompt for LaTeX generation
latex_prompt = ChatPromptTemplate.from_template(
    """Generate a complete LaTeX document about: {topic}

Requirements:
- Include proper document structure with \\documentclass{{article}}, \\begin{{document}}, \\end{{document}}
- Add required packages: \\usepackage{{booktabs, float, hyperref, geometry, amsmath, amssymb, array, tabularx}}
- Set proper margins: \\geometry{{margin=1in}}
- Add ONLY the title (derived from the topic) and date (\\today) - DO NOT add any author or subtitle
- Use \\maketitle for proper title formatting
- Include sections and subsections with descriptive headings
- DO NOT include any subtitle, author name, or agent attribution in the document
- DO NOT include any images or figures in the document

TABLE FORMATTING (CRITICAL):
- Use tabularx for responsive tables: \\begin{{tabularx}}{{\\textwidth}}{{l X X X}} for flexible columns
- OR use tabular with proper column widths: \\begin{{tabular}}{{p{{3cm}}p{{4cm}}p{{3cm}}p{{4cm}}}}
- Always use booktabs: \\toprule, \\midrule, \\bottomrule
- Wrap tables in \\begin{{table}}[H] with \\centering
- Add \\caption and \\label for each table
- Use \\renewcommand{{\\arraystretch}}{{1.3}} before tables for better row spacing
- For long text in cells, use p{{Xcm}} column type instead of c or l

- Use proper text alignment and paragraph spacing
- Include itemize/enumerate lists where appropriate
- Add meaningful content (3-4 pages worth)
- Use proper LaTeX formatting for emphasis (\\textbf{{}}, \\textit{{}}, \\emph{{}})
- Include a bibliography or references section if applicable

Document Structure:
1. Title page (title and date ONLY - no author/subtitle)
2. Abstract (brief summary)
3. Introduction
4. Main sections with subsections
5. Tables with captions (NO images/figures)
6. Conclusion
7. References (if applicable)

Return ONLY the LaTeX code, no explanations or markdown formatting."""
)

# Create chain
latex_chain = latex_prompt | latex_model
