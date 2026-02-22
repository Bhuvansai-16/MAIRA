import { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import {
  Plus,
  Search,
  FileText,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  X,
  Send,
  Sparkles,
  RefreshCw,
  Download,
  Wand2,
  PanelRightOpen,
  PanelLeftOpen,
  ArrowLeft,
  File,
  Trash2,
  Check,
  Copy,
  Eye,
  EyeOff,
  Layout,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { toast } from 'sonner';
import { basicSetup } from 'codemirror';
import { EditorView, ViewUpdate, keymap } from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { oneDark } from '@codemirror/theme-one-dark';
import { indentWithTab } from '@codemirror/commands';
import './PaperWriter.css';
import { jsPDF } from "jspdf";
import * as docx from "docx";
import { saveAs } from "file-saver";
import Lenis from 'lenis';
import { latex } from 'codemirror-lang-latex';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Bold,
  Italic,
  Underline,
  Quote,
  List,
  Link as LinkIcon,
  Image as ImageIcon,
  Heading1,
  Heading2,
  Code,
  Table,
} from 'lucide-react';

// ─── LaTeX templates ───────────────────────────────────
const TEMPLATES: Record<string, { name: string; description: string; icon: string; content: string }> = {
  article: {
    name: 'Research Article',
    description: 'Standard single-column article with numbered sections',
    icon: '📄',
    content: `\\documentclass[11pt,a4paper]{article} % oneside by default
\\usepackage[utf8]{inputenc}
\\usepackage[T1]{fontenc}
\\usepackage{lmodern}
\\usepackage{amsmath,amssymb,amsfonts}
\\usepackage{graphicx}
\\usepackage{booktabs}
\\usepackage{hyperref}
\\usepackage{natbib} % or biblatex for modern bibliography

\\title{Your Research Article Title}
\\author{Your Name\\\\
        Affiliation\\\\
        \\texttt{email@example.com}}
\\date{\\today}

\\begin{document}

\\maketitle

\\begin{abstract}
Your abstract here. Summarize the research problem, methods, results, and conclusions.
\\end{abstract}

\\section{Introduction}
Background, motivation, and objectives.

\\section{Related Work}
Literature review.

\\section{Methods}
Detailed methodology.

\\section{Results}
Findings with tables/figures.

\\section{Discussion}
Interpretation and implications.

\\section{Conclusion}
Summary and future work.

\\bibliographystyle{plainnat}
\\bibliography{references} % your .bib file

\\end{document}`,
  },
  ieee: {
    name: 'IEEE Conference',
    description: 'Two-column IEEE conference format with keywords',
    icon: '🔬',
    content: `\\documentclass[conference]{IEEEtran}
\\IEEEoverridecommandlockouts
% The following packages are recommended/commonly used
\\usepackage{cite}
\\usepackage{amsmath,amssymb,amsfonts}
\\usepackage{algorithmic}
\\usepackage{graphicx}
\\usepackage{textcomp}
\\usepackage{xcolor}
\\usepackage{balance} % For balancing columns on the last page
\\usepackage{hyperref}

% Optional: If you need A4 paper (not standard for IEEE)
% \\documentclass[conference,a4paper]{IEEEtran}

\\title{Your Paper Title}

\\author{\\IEEEauthorblockN{Author Name(s)}
\\IEEEauthorblockA{\\textit{Affiliation} \\\\
\\textit{Institution/University} \\\\
\\textit{City, Country} \\\\
\\texttt{email@example.com}}
}

\\begin{document}

\\maketitle

\\begin{abstract}
Your abstract here (typically 150-200 words). Summarize purpose, methods, results, and conclusions.
\\end{abstract}

\\begin{IEEEkeywords}
Keyword1, Keyword2, Keyword3, Keyword4
\\end{IEEEkeywords}

\\section{Introduction}
Your introduction, background, and motivation.

\\section{Related Work}
Review of prior research.

\\section{Methodology}
Detailed description of your approach.

\\section{Results}
Present findings with tables, figures, and equations.

\\section{Conclusion}
Summary and future work.

% Balance columns on last page (recommended for IEEE)
\\balance

\\bibliographystyle{IEEEtran}
\\bibliography{references} % Use your .bib file here

\\end{document}`,
  },
  thesis: {
    name: 'Thesis Chapter',
    description: 'Chapter structure for thesis/dissertation',
    icon: '📚',
    content: `\\documentclass[12pt,a4paper]{report} % oneside by default; use 'book' for twoside in full thesis
\\usepackage[utf8]{inputenc}
\\usepackage[T1]{fontenc}
\\usepackage{lmodern}
\\usepackage{amsmath,amssymb}
\\usepackage{graphicx}
\\usepackage{booktabs}
\\usepackage{hyperref}
\\usepackage{chapterbib} % optional: per-chapter bibliography

\\begin{document}

\\chapter{Your Chapter Title} % e.g., Introduction or Methods

\\section{Section Title}
Your content.

\\subsection{Subsection}
Details.

% Example figure (spans single column)
\\begin{figure}[htbp]
\\centering
\\includegraphics[width=0.8\\textwidth]{example-image}
\\caption{Your caption.}
\\label{fig:example}
\\end{figure}

% Example table
\\begin{table}[htbp]
\\centering
\\begin{tabular}{ccc}
\\toprule
Header1 & Header2 & Header3 \\\\
\\midrule
Data1 & Data2 & Data3 \\\\
\\bottomrule
\\end{tabular}
\\caption{Your table caption.}
\\end{table}

Continue your chapter...

% Optional per-chapter bibliography
%\\bibliographystyle{plain}
%\\bibliography{references}

\\end{document}`,
  },
  blank: {
    name: 'Blank Document',
    description: 'Start from scratch with minimal setup',
    icon: '📝',
    content: `\\documentclass[11pt,a4paper]{article} % oneside by default
\\usepackage[utf8]{inputenc}
\\usepackage[T1]{fontenc}
\\usepackage{lmodern}
\\usepackage{amsmath}
\\usepackage{graphicx}
\\usepackage{hyperref}

\\title{Your Document Title}
\\author{Your Name}
\\date{\\today}

\\begin{document}

\\maketitle

Your content starts here. Add sections, text, figures, etc.

\\end{document}`,
  },
};

// ─── Parse LaTeX to outline items ──────────────────────
interface OutlineItem {
  label: string;
  level: number;
  line: number;
}

function parseOutline(latex: string): OutlineItem[] {
  const lines = latex.split('\n');
  const items: OutlineItem[] = [];
  const sectionRegex = /\\(chapter|section|subsection|subsubsection)\*?\{([^}]+)\}/;

  const levelMap: Record<string, number> = {
    chapter: 0,
    section: 1,
    subsection: 2,
    subsubsection: 3,
  };

  lines.forEach((line, idx) => {
    const match = line.match(sectionRegex);
    if (match) {
      items.push({
        label: match[2],
        level: levelMap[match[1]] ?? 1,
        line: idx + 1,
      });
    }
  });

  return items;
}

// ─── Simple LaTeX to HTML preview ──────────────────────
function renderPreview(latex: string): string {
  let html = latex;

  // Extract title, author, date
  const titleMatch = html.match(/\\title\{([^}]+)\}/);
  const authorMatch = html.match(/\\author\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/s);

  // Remove preamble (everything before \begin{document})
  const beginDoc = html.indexOf('\\begin{document}');
  const endDoc = html.indexOf('\\end{document}');
  if (beginDoc !== -1) {
    html = html.substring(beginDoc + '\\begin{document}'.length);
  }
  if (endDoc !== -1) {
    html = html.substring(0, html.indexOf('\\end{document}'));
  }

  // Handle titlepage environment
  html = html.replace(/\\begin\{titlepage\}[\s\S]*?\\end\{titlepage\}/g, (match) => {
    let tp = match;
    tp = tp.replace(/\\begin\{titlepage\}|\\end\{titlepage\}/g, '');
    tp = tp.replace(/\\centering/g, '');
    tp = tp.replace(/\\vspace\*?\{[^}]+\}/g, '');
    tp = tp.replace(/\{\\LARGE\\bfseries\s*([\s\S]*?)\\par\}/g, '<h1 style="text-align:center;font-size:24pt;margin:32px 0 16px;">$1</h1>');
    tp = tp.replace(/\{\\Large\s*([\s\S]*?)\\par\}/g, '<p style="text-align:center;font-size:14pt;color:#444;">$1</p>');
    tp = tp.replace(/\{\\large\s*([\s\S]*?)\\par\}/g, '<p style="text-align:center;font-size:12pt;color:#555;">$1</p>');
    tp = tp.replace(/\\\\/g, '<br>');
    return `<div class="pw-preview-titlepage">${tp}</div>`;
  });

  // Handle \maketitle
  if (html.includes('\\maketitle')) {
    let titleBlock = '';
    if (titleMatch) {
      titleBlock += `<h1>${titleMatch[1]}</h1>`;
    }
    if (authorMatch) {
      let authorText = authorMatch[1]
        .replace(/\\\\/g, ', ')
        .replace(/\\small\s*/g, '')
        .replace(/\\textit\{([^}]+)\}/g, '$1')
        .replace(/\\textsuperscript\{[^}]*\}/g, '')
        .replace(/\\IEEEauthorblockN\{([^}]+)\}/g, '<strong>$1</strong>')
        .replace(/\\IEEEauthorblockA\{([^}]*(?:\{[^}]*\}[^}]*)*)\}/gs, (_, inner) => {
          const cleaned = inner.replace(/\\textit\{([^}]+)\}/g, '$1').replace(/\\\\/g, ', ').replace(/\s+/g, ' ').trim();
          return `<span style="font-size:9pt;color:#666;">${cleaned}</span>`;
        })
        .replace(/\\and/g, ' &nbsp;&nbsp; ')
        .replace(/\s+/g, ' ')
        .trim();
      titleBlock += `<p class="pw-preview-authors">${authorText}</p>`;
    }
    html = html.replace('\\maketitle', titleBlock);
  }

  // Abstract
  html = html.replace(
    /\\begin\{abstract\}([\s\S]*?)\\end\{abstract\}/g,
    '<div class="pw-preview-abstract"><strong>Abstract — </strong>$1</div>'
  );

  // IEEEkeywords
  html = html.replace(
    /\\begin\{IEEEkeywords\}([\s\S]*?)\\end\{IEEEkeywords\}/g,
    '<p style="font-style:italic;color:#555;font-size:9.5pt;margin-bottom:16px;"><strong>Index Terms — </strong>$1</p>'
  );

  // Table of contents placeholder
  html = html.replace(/\\tableofcontents/g, '<div style="text-align:center;color:#888;padding:24px;border:1px dashed #ccc;margin:16px 0;border-radius:4px;font-size:10pt;">— Table of Contents (generated on compile) —</div>');

  // Sections
  html = html.replace(/\\chapter\*?\{([^}]+)\}/g, '<h1>$1</h1>');
  html = html.replace(/\\section\*?\{([^}]+)\}/g, '<h2>$1</h2>');
  html = html.replace(/\\subsection\*?\{([^}]+)\}/g, '<h3>$1</h3>');
  html = html.replace(/\\subsubsection\*?\{([^}]+)\}/g, '<h4 style="font-size:11pt;font-weight:600;margin-top:12px;">$1</h4>');

  // Text formatting
  html = html.replace(/\\textbf\{([^}]+)\}/g, '<strong>$1</strong>');
  html = html.replace(/\\textit\{([^}]+)\}/g, '<em>$1</em>');
  html = html.replace(/\\emph\{([^}]+)\}/g, '<em>$1</em>');
  html = html.replace(/\\underline\{([^}]+)\}/g, '<u>$1</u>');
  html = html.replace(/\\textsuperscript\{([^}]*)\}/g, '<sup>$1</sup>');
  html = html.replace(/\\textsubscript\{([^}]*)\}/g, '<sub>$1</sub>');

  // Math (inline)
  html = html.replace(/\$([^$]+)\$/g, '<code class="pw-math">$1</code>');

  // Equations
  html = html.replace(/\\begin\{equation\}([\s\S]*?)\\end\{equation\}/g,
    '<div class="pw-preview-equation"><code>$1</code></div>');

  // Tables
  html = html.replace(/\\begin\{table\}[\s\S]*?\\caption\{([^}]*)\}[\s\S]*?\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}[\s\S]*?\\end\{table\}/g,
    (_, caption, body) => {
      let tableHtml = '<div class="pw-preview-table-wrap">';
      tableHtml += `<table class="pw-preview-table">`;
      const rows = body.split('\\\\').filter((r: string) => r.trim() && !r.includes('\\toprule') && !r.includes('\\midrule') && !r.includes('\\bottomrule') && !r.includes('\\hline'));
      rows.forEach((row: string, i: number) => {
        const cells = row.split('&').map((c: string) => c.replace(/\\textbf\{([^}]+)\}/g, '<strong>$1</strong>').trim());
        const tag = i === 0 ? 'th' : 'td';
        tableHtml += '<tr>' + cells.map((c: string) => `<${tag}>${c}</${tag}>`).join('') + '</tr>';
      });
      tableHtml += '</table>';
      if (caption) tableHtml += `<p class="pw-preview-caption">${caption}</p>`;
      tableHtml += '</div>';
      return tableHtml;
    });

  // Standalone tabular (without table environment)
  html = html.replace(/\\begin\{tabular\}\{[^}]*\}([\s\S]*?)\\end\{tabular\}/g,
    (_, body) => {
      let tableHtml = '<table class="pw-preview-table">';
      const rows = body.split('\\\\').filter((r: string) => r.trim() && !r.includes('\\toprule') && !r.includes('\\midrule') && !r.includes('\\bottomrule') && !r.includes('\\hline'));
      rows.forEach((row: string, i: number) => {
        const cells = row.split('&').map((c: string) => c.replace(/\\textbf\{([^}]+)\}/g, '<strong>$1</strong>').trim());
        const tag = i === 0 ? 'th' : 'td';
        tableHtml += '<tr>' + cells.map((c: string) => `<${tag}>${c}</${tag}>`).join('') + '</tr>';
      });
      tableHtml += '</table>';
      return tableHtml;
    });

  // Bibliography
  html = html.replace(/\\begin\{thebibliography\}\{[^}]*\}([\s\S]*?)\\end\{thebibliography\}/g,
    (_, body) => {
      let refs = '<div class="pw-preview-references"><h2>References</h2><ol>';
      const items = body.split('\\bibitem').filter((s: string) => s.trim());
      items.forEach((item: string) => {
        const cleaned = item.replace(/\{[^}]*\}\s*/, '').replace(/\\textit\{([^}]+)\}/g, '<em>$1</em>').trim();
        if (cleaned) refs += `<li>${cleaned}</li>`;
      });
      refs += '</ol></div>';
      return refs;
    });

  // Lists
  html = html.replace(/\\begin\{enumerate\}/g, '<ol>');
  html = html.replace(/\\end\{enumerate\}/g, '</ol>');
  html = html.replace(/\\begin\{itemize\}/g, '<ul>');
  html = html.replace(/\\end\{itemize\}/g, '</ul>');
  html = html.replace(/\\item\s*(.*)/g, '<li>$1</li>');

  // Labels and refs
  html = html.replace(/\\label\{[^}]+\}/g, '');
  html = html.replace(/\\cite\{([^}]+)\}/g, '<span style="color:#7c3aed;">[$1]</span>');
  html = html.replace(/\\ref\{([^}]+)\}/g, '<span style="color:#6366f1;">[$1]</span>');
  html = html.replace(/Fig\.~\\ref/g, 'Fig. ');
  html = html.replace(/Table~\\ref/g, 'Table ');

  // Remove remaining LaTeX commands
  html = html.replace(/\\bibliographystyle\{[^}]+\}/g, '');
  html = html.replace(/\\bibliography\{[^}]+\}/g, '');
  html = html.replace(/\\usepackage(\[[^\]]*\])?\{[^}]+\}/g, '');
  html = html.replace(/\\doublespacing/g, '');
  html = html.replace(/\\setlength\{[^}]+\}\{[^}]+\}/g, '');
  html = html.replace(/\\pagestyle\{[^}]+\}/g, '');
  html = html.replace(/\\fancyhf\{[^}]*\}/g, '');
  html = html.replace(/\\fancyhead\[[^\]]*\]\{[^}]*\}/g, '');
  html = html.replace(/\\fancyfoot\[[^\]]*\]\{[^}]*\}/g, '');
  html = html.replace(/\\renewcommand\{[^}]+\}\{[^}]*\}/g, '');
  html = html.replace(/\\def\\[^\n]+/g, '');
  html = html.replace(/\\IEEEoverridecommandlockouts/g, '');
  html = html.replace(/\\newpage/g, '<hr style="border:none;border-top:1px dashed #ddd;margin:24px 0;">');
  html = html.replace(/\\footnotesize/g, '');
  html = html.replace(/\\centering/g, '');

  // Convert double newlines to paragraphs
  const paragraphs = html.split(/\n\n+/);
  html = paragraphs
    .map((p) => {
      const trimmed = p.trim();
      if (!trimmed) return '';
      if (
        trimmed.startsWith('<h') ||
        trimmed.startsWith('<div') ||
        trimmed.startsWith('<ol') ||
        trimmed.startsWith('<ul') ||
        trimmed.startsWith('<table') ||
        trimmed.startsWith('<p ') ||
        trimmed.startsWith('<hr') ||
        trimmed.startsWith('<li')
      ) {
        return trimmed;
      }
      return `<p>${trimmed}</p>`;
    })
    .join('\n');

  // Clean up remaining backslash commands
  html = html.replace(/%[^\n]*/g, ''); // comments
  html = html.replace(/\\\\/g, '<br>');

  return html;
}

// ─── File interface ────────────────────────────────────
interface PaperFile {
  id: string;
  name: string;
  content: string;
  type: 'tex' | 'bib' | 'image';
}

// ─── Chat message interface ────────────────────────────
interface ChatMessage {
  id: string;
  role: 'user' | 'ai';
  text: string;
  updatedLatex?: string | null;
  changeType?: string;
  applied?: boolean;
}

// ─── Component ─────────────────────────────────────────
export const PaperWriter = () => {
  // ── File state ──
  const [files, setFiles] = useState<PaperFile[]>([]);
  const [activeFileId, setActiveFileId] = useState<string | null>(null);
  const [showNewFileModal, setShowNewFileModal] = useState(false);
  const [newFileName, setNewFileName] = useState('');
  const [showTemplates, setShowTemplates] = useState(true);
  const { theme } = useTheme();

  // ── Navigation ──
  // (Back button logic moved to render)

  // ── Sidebar state ──
  const [sidebarTab, setSidebarTab] = useState<'files' | 'chats'>('files');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [outlineOpen, setOutlineOpen] = useState(true);

  // ── Preview state ──
  const [previewCollapsed, setPreviewCollapsed] = useState(false);
  const [isCompiling, setIsCompiling] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');

  // ── Chat state ──
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'ai',
      text: "Hello! I'm your AI writing assistant. I can help you:\n\n• **Add sections** — \"Add an introduction about neural networks\"\n• **Edit content** — \"Change the title to 'Deep Learning Survey'\"\n• **Fix formatting** — \"Fix the table alignment\"\n• **Add elements** — \"Add a comparison table with 3 methods\"\n\nJust describe what you'd like to change!",
    },
  ]);
  const [chatInput, setChatInput] = useState('');
  const [aiThinking, setAiThinking] = useState(false);

  // ── Resizing state ──
  const [sidebarWidth, setSidebarWidth] = useState(300);
  const [previewWidth, setPreviewWidth] = useState(500);
  const [resizing, setResizing] = useState<'sidebar' | 'preview' | null>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizing) return;
      if (resizing === 'sidebar') {
        setSidebarWidth(Math.max(200, Math.min(800, e.clientX)));
      } else {
        setPreviewWidth(Math.max(300, Math.min(1200, window.innerWidth - e.clientX)));
      }
    };
    const handleMouseUp = () => setResizing(null);

    if (resizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
    } else {
      document.body.style.cursor = '';
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
    };
  }, [resizing]);

  // ── Layout state ──
  const [showLayoutMenu, setShowLayoutMenu] = useState(false);

  const applyLayout = (type: 'standard' | 'coding' | 'review') => {
    const w = window.innerWidth;
    if (type === 'standard') {
      setSidebarCollapsed(false);
      setPreviewCollapsed(false);
      setSidebarWidth(Math.max(250, w * 0.15));
      setPreviewWidth(w * 0.40);
    } else if (type === 'coding') {
      setSidebarCollapsed(true);
      setPreviewCollapsed(false);
      setPreviewWidth(w * 0.25);
    } else if (type === 'review') {
      setSidebarCollapsed(true);
      setPreviewCollapsed(false);
      setPreviewWidth(w * 0.70);
    }
    setShowLayoutMenu(false);
  };

  // ── Export menu state ──
  const [showExportMenu, setShowExportMenu] = useState(false);

  // ── Editor refs ──
  const editorContainerRef = useRef<HTMLDivElement>(null);
  const editorViewRef = useRef<EditorView | null>(null);

  const scrollToLine = useCallback((line: number) => {
    if (!editorViewRef.current) return;
    const view = editorViewRef.current;

    // CodeMirror lines are 1-indexed
    const docLines = view.state.doc.lines;
    const targetLine = Math.min(Math.max(1, line), docLines);

    const lineInfo = view.state.doc.line(targetLine);

    view.dispatch({
      effects: EditorView.scrollIntoView(lineInfo.from, { y: 'center' }),
      selection: { anchor: lineInfo.from },
    });
    view.focus();
  }, []);

  const insertFormat = useCallback((type: string) => {
    if (!editorViewRef.current) return;
    const view = editorViewRef.current;
    const { from, to } = view.state.selection.main;
    const text = view.state.sliceDoc(from, to);

    let insert = '';
    let cursorOffset = 0;

    switch (type) {
      case 'bold': insert = `\\textbf{${text}}`; cursorOffset = 8; break;
      case 'italic': insert = `\\textit{${text}}`; cursorOffset = 8; break;
      case 'underline': insert = `\\underline{${text}}`; cursorOffset = 11; break;
      case 'quote': insert = `\\begin{quote}\n${text}\n\\end{quote}`; cursorOffset = 14; break;
      case 'list': insert = `\\begin{itemize}\n  \\item ${text}\n\\end{itemize}`; cursorOffset = 18; break;
      case 'h1': insert = `\\section{${text}}`; cursorOffset = 9; break;
      case 'h2': insert = `\\subsection{${text}}`; cursorOffset = 12; break;
      case 'code': insert = `\\texttt{${text}}`; cursorOffset = 8; break;
      case 'link': insert = `\\href{url}{${text}}`; cursorOffset = 6; break;
      case 'image': insert = `\\includegraphics[width=0.8\\textwidth]{filename}`; cursorOffset = 28; break;
      case 'table': insert = `\\begin{table}[ht]\n  \\centering\n  \\begin{tabular}{c c}\n    A & B \\\\\n    C & D\n  \\end{tabular}\n  \\caption{Caption}\n  \\label{tab:my_label}\n\\end{table}`; cursorOffset = 0; break;
      default: return;
    }

    view.dispatch({
      changes: { from, to, insert },
      selection: { anchor: from + cursorOffset },
    });
    view.focus();
  }, []);
  const compileTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const previewBodyRef = useRef<HTMLDivElement>(null);
  const lenisInstances = useRef<any[]>([]);

  const activeFile = files.find((f) => f.id === activeFileId);
  const outline = activeFile ? parseOutline(activeFile.content) : [];

  // ── Lenis RAF Loop ──
  useEffect(() => {
    let reqId: number;
    const raf = (time: number) => {
      lenisInstances.current.forEach((l) => l.raf(time));
      reqId = requestAnimationFrame(raf);
    };
    reqId = requestAnimationFrame(raf);
    return () => cancelAnimationFrame(reqId);
  }, []);

  // ── Lenis for Preview ──
  useEffect(() => {
    if (!previewBodyRef.current || previewCollapsed) return;

    const lenis = new Lenis({
      wrapper: previewBodyRef.current,
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      gestureOrientation: 'vertical',
      smoothWheel: true,
    });

    lenisInstances.current.push(lenis);

    return () => {
      lenis.destroy();
      lenisInstances.current = lenisInstances.current.filter((l) => l !== lenis);
    };
  }, [previewCollapsed, theme]); // Re-init on theme/collapse change if needed

  // ── Auto scroll chat ──
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, aiThinking]);

  // ── Init/Update CodeMirror ──
  useEffect(() => {
    if (!editorContainerRef.current || !activeFile) return;

    // Destroy previous editor
    if (editorViewRef.current) {
      editorViewRef.current.destroy();
      editorViewRef.current = null;
    }

    const state = EditorState.create({
      doc: activeFile.content,
      extensions: [
        basicSetup,
        oneDark,
        keymap.of([indentWithTab]),
        EditorView.lineWrapping,
        EditorView.updateListener.of((update: ViewUpdate) => {
          if (update.docChanged) {
            const newContent = update.state.doc.toString();
            setFiles((prev) =>
              prev.map((f) =>
                f.id === activeFile.id ? { ...f, content: newContent } : f
              )
            );
            // Debounce compile
            if (compileTimeoutRef.current) clearTimeout(compileTimeoutRef.current);
            setIsCompiling(true);
            compileTimeoutRef.current = setTimeout(() => {
              setPreviewHtml(renderPreview(newContent));
              setIsCompiling(false);
            }, 600);
          }
        }),
        EditorView.theme({
          '&': {
            backgroundColor: 'transparent'
          },
          '.cm-gutters': { backgroundColor: 'transparent' },
          '.cm-activeLine': { backgroundColor: 'rgba(124, 58, 237, 0.04)' },
        }),
        latex(),
      ],
    });

    const view = new EditorView({
      state,
      parent: editorContainerRef.current,
    });

    editorViewRef.current = view;

    // Attach Lenis to Editor
    const lenis = new Lenis({
      wrapper: view.scrollDOM,
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      gestureOrientation: 'vertical',
      smoothWheel: true,
    });
    lenisInstances.current.push(lenis);

    // Initial compile
    setPreviewHtml(renderPreview(activeFile.content));

    return () => {
      lenis.destroy();
      lenisInstances.current = lenisInstances.current.filter((l) => l !== lenis);
      view.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFileId, theme]);

  // ── Create file from template ──
  const createFromTemplate = useCallback(
    (templateKey: string) => {
      const template = TEMPLATES[templateKey];
      if (!template) return;

      const id = `file_${Date.now()}`;
      const newFile: PaperFile = {
        id,
        name: templateKey === 'blank' ? 'main.tex' : `${templateKey}_paper.tex`,
        content: template.content,
        type: 'tex',
      };

      setFiles((prev) => [...prev, newFile]);
      setActiveFileId(id);
      setShowTemplates(false);
    },
    []
  );

  // ── Create new file ──
  const createNewFile = useCallback(() => {
    if (!newFileName.trim()) return;
    const name = newFileName.endsWith('.tex') ? newFileName : `${newFileName}.tex`;
    const id = `file_${Date.now()}`;
    const newFile: PaperFile = {
      id,
      name,
      content: TEMPLATES.blank.content,
      type: 'tex',
    };
    setFiles((prev) => [...prev, newFile]);
    setActiveFileId(id);
    setShowNewFileModal(false);
    setNewFileName('');
    setShowTemplates(false);
  }, [newFileName]);

  // ── Delete file ──
  const deleteFile = useCallback(
    (fileId: string) => {
      setFiles((prev) => prev.filter((f) => f.id !== fileId));
      if (activeFileId === fileId) {
        const remaining = files.filter((f) => f.id !== fileId);
        setActiveFileId(remaining.length > 0 ? remaining[0].id : null);
        if (remaining.length === 0) setShowTemplates(true);
      }
    },
    [activeFileId, files]
  );

  // ── Update editor content programmatically ──
  const updateEditorContent = useCallback((newContent: string) => {
    if (editorViewRef.current) {
      const view = editorViewRef.current;
      view.dispatch({
        changes: {
          from: 0,
          to: view.state.doc.length,
          insert: newContent,
        },
      });
    }
    // Also update state
    setFiles((prev) =>
      prev.map((f) =>
        f.id === activeFileId ? { ...f, content: newContent } : f
      )
    );
    setPreviewHtml(renderPreview(newContent));
  }, [activeFileId]);



  // ── Chat send ──
  const sendChatMessage = useCallback(async () => {
    if (!chatInput.trim()) return;
    const userMsg: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      text: chatInput,
    };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput('');
    setAiThinking(true);

    try {
      const historyForApi = chatMessages.slice(-6).map(m => ({
        role: m.role,
        text: m.text,
      }));

      const response = await axios.post('http://localhost:8000/paper-writer/chat', {
        message: userMsg.text,
        session_id: 'default-session',
        paper_content: activeFile ? activeFile.content : undefined,
        chat_history: historyForApi,
      });

      // Automatically apply changes if provided
      const newLatex = response.data.updated_latex;
      if (newLatex) {
        updateEditorContent(newLatex);
      }

      const aiMsg: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        role: 'ai',
        text: response.data.response,
        updatedLatex: newLatex,
        changeType: response.data.change_type,
        applied: !!newLatex,
      };
      setChatMessages((prev) => [...prev, aiMsg]);
    } catch (error) {
      console.error("Failed to get AI response:", error);
      const errorMsg: ChatMessage = {
        id: `msg_${Date.now() + 1}`,
        role: 'ai',
        text: "Sorry, I couldn't connect to the AI server. Please make sure the backend is running on port 8000.",
      };
      setChatMessages((prev) => [...prev, errorMsg]);
      toast.error("Failed to connect to AI server");
    } finally {
      setAiThinking(false);
    }
  }, [chatInput, activeFile, chatMessages, updateEditorContent]);

  // ── Export helpers (Client-side) ──
  const exportToPdf = useCallback(async () => {
    const element = document.querySelector('.pw-preview-page') as HTMLElement;
    if (!element) {
      alert("Please expand the preview panel to export PDF.");
      return;
    }

    const doc = new jsPDF({
      unit: 'pt',
      format: 'a4',
      orientation: 'portrait'
    });

    await doc.html(element, {
      callback: (doc) => {
        doc.save(`${activeFile?.name.replace('.tex', '') || 'document'}.pdf`);
      },
      x: 40,
      y: 40,
      width: 500,
      windowWidth: 800
    });
  }, [activeFile]);

  const exportToDocx = useCallback(async () => {
    if (!previewHtml) {
      alert("No content to export. Please ensure the document is compiled.");
      return;
    }

    try {
      const parser = new DOMParser();
      const htmlDoc = parser.parseFromString(previewHtml, 'text/html');
      const nodes = Array.from(htmlDoc.body.children);

      const docChildren: (docx.Paragraph | docx.Table)[] = [];

      // Helper to process inline text with formatting
      const retrieveTextRuns = (el: Element): docx.TextRun[] => {
        const runs: docx.TextRun[] = [];
        el.childNodes.forEach(node => {
          if (node.nodeType === Node.TEXT_NODE) {
            const text = node.textContent || "";
            if (text) runs.push(new docx.TextRun(text));
          } else if (node.nodeType === Node.ELEMENT_NODE) {
            const element = node as HTMLElement;
            const tag = element.tagName;
            const text = element.textContent || "";

            // Handle line breaks
            if (tag === 'BR') {
              runs.push(new docx.TextRun({ break: 1 }));
              return;
            }

            runs.push(new docx.TextRun({
              text,
              bold: tag === 'STRONG' || tag === 'B',
              italics: tag === 'EM' || tag === 'I' || tag === 'CITE',
            }));
          }
        });
        return runs;
      };

      // Recursive function to process blocks
      const processNode = (node: Node): (docx.Paragraph | docx.Table)[] => {
        if (node.nodeType !== Node.ELEMENT_NODE) return [];
        const el = node as HTMLElement;
        const tag = el.tagName;

        const paragraphs: (docx.Paragraph | docx.Table)[] = [];

        if (['H1', 'H2', 'H3', 'H4', 'H5', 'H6'].includes(tag)) {
          const levels: Record<string, any> = {
            'H1': docx.HeadingLevel.HEADING_1,
            'H2': docx.HeadingLevel.HEADING_2,
            'H3': docx.HeadingLevel.HEADING_3,
            'H4': docx.HeadingLevel.HEADING_4,
            'H5': docx.HeadingLevel.HEADING_5,
            'H6': docx.HeadingLevel.HEADING_6,
          };
          paragraphs.push(new docx.Paragraph({
            text: el.textContent || "",
            heading: levels[tag]
          }));
        } else if (tag === 'P') {
          paragraphs.push(new docx.Paragraph({
            children: retrieveTextRuns(el)
          }));
        } else if (tag === 'UL' || tag === 'OL') {
          Array.from(el.children).forEach(li => {
            paragraphs.push(new docx.Paragraph({
              children: retrieveTextRuns(li),
              bullet: { level: 0 }
            }));
          });
        } else if (tag === 'DIV' || tag === 'SECTION' || tag === 'ARTICLE') {
          // Check if it has block children
          const hasBlocks = Array.from(el.children).some(c =>
            ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'P', 'DIV', 'UL', 'OL'].includes(c.tagName)
          );

          if (hasBlocks) {
            // Recurse
            Array.from(el.children).forEach(child => {
              paragraphs.push(...processNode(child));
            });
          } else {
            // Treat as paragraph
            paragraphs.push(new docx.Paragraph({
              children: retrieveTextRuns(el)
            }));
          }
          const rows: docx.TableRow[] = [];
          const trs = Array.from(el.querySelectorAll('tr'));

          trs.forEach(tr => {
            const cells: docx.TableCell[] = [];
            const tds = Array.from(tr.querySelectorAll('th, td'));

            tds.forEach(td => {
              cells.push(new docx.TableCell({
                children: [new docx.Paragraph({
                  children: retrieveTextRuns(td as HTMLElement)
                })],
                borders: {
                  top: { style: docx.BorderStyle.SINGLE, size: 1, color: "888888" },
                  bottom: { style: docx.BorderStyle.SINGLE, size: 1, color: "888888" },
                  left: { style: docx.BorderStyle.SINGLE, size: 1, color: "888888" },
                  right: { style: docx.BorderStyle.SINGLE, size: 1, color: "888888" },
                },
                margins: {
                  top: 100,
                  bottom: 100,
                  left: 100,
                  right: 100,
                }
              }));
            });

            rows.push(new docx.TableRow({
              children: cells
            }));
          });

          paragraphs.push(new docx.Table({
            rows: rows,
            width: {
              size: 100,
              type: docx.WidthType.PERCENTAGE,
            },
          }));
        }

        return paragraphs;
      };

      nodes.forEach(node => {
        docChildren.push(...processNode(node));
      });

      const doc = new docx.Document({
        sections: [{
          children: docChildren
        }]
      });

      const blob = await docx.Packer.toBlob(doc);
      saveAs(blob, `${activeFile?.name.replace('.tex', '') || 'document'}.docx`);

    } catch (error) {
      console.error("Export failed:", error);
      toast.error("Failed to export DOCX");
    }
  }, [previewHtml, activeFile]);

  // ── Export functions ──
  const exportFile = useCallback((format: 'tex' | 'copy' | 'pdf' | 'doc') => {
    if (!activeFile) return;
    setShowExportMenu(false);

    if (format === 'copy') {
      navigator.clipboard.writeText(activeFile.content);
      return;
    }

    if (format === 'pdf') {
      exportToPdf();
      return;
    }

    if (format === 'doc') {
      exportToDocx();
      return;
    }

    // Download as .tex file
    const blob = new Blob([activeFile.content], { type: 'application/x-tex' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = activeFile.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [activeFile]);

  // ── Render: Template selection screen ──
  if (showTemplates) {
    return (
      <div className="pw-root">
        {/* Top bar */}
        <div className="pw-topbar">
          <div className="pw-topbar-left">
            <Link to="/" className="pw-topbar-logo">
              <img src="/DarkLogo.png" alt="MAIRA" className="h-20 w-auto object-contain block dark:hidden" />
              <img src="/Logo.png" alt="MAIRA" className="h-20 w-auto object-contain hidden dark:block" />
            </Link>
          </div>
          <div className="pw-topbar-right">
            <Link to="/" className="pw-topbar-btn">
              <ArrowLeft size={14} />
              Back to Home
            </Link>
          </div>
        </div>

        {/* Template selection */}
        <div className="pw-template-selection">
          <div style={{ textAlign: 'center', maxWidth: 560 }}>
            <div className="pw-hero-icon">
              <Sparkles size={32} color="#a78bfa" />
            </div>
            <h1 className="pw-hero-title">Write Your Research Paper</h1>
            <p className="pw-hero-subtitle">
              Choose a template to get started. Our AI assistant will help you draft, refine, and perfect your paper.
            </p>
          </div>

          <div className="pw-templates-grid" style={{ maxWidth: 640, width: '100%' }}>
            {Object.entries(TEMPLATES).map(([key, tmpl]) => (
              <div
                key={key}
                className="pw-template-card"
                onClick={() => createFromTemplate(key)}
              >
                <div className="pw-template-card-icon">{tmpl.icon}</div>
                <div>
                  <h4>{tmpl.name}</h4>
                  <p>{tmpl.description}</p>
                </div>
              </div>
            ))}
          </div>

          <button
            className="pw-topbar-btn"
            onClick={() => setShowNewFileModal(true)}
            style={{ marginTop: 12 }}
          >
            <Plus size={14} />
            Create blank file
          </button>
        </div>

        {/* New file modal */}
        {showNewFileModal && (
          <div className="pw-modal-overlay" onClick={() => setShowNewFileModal(false)}>
            <div className="pw-modal" onClick={(e) => e.stopPropagation()}>
              <h3>Create New File</h3>
              <input
                className="pw-modal-input"
                placeholder="e.g. main.tex"
                value={newFileName}
                onChange={(e) => setNewFileName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && createNewFile()}
                autoFocus
              />
              <div className="pw-modal-actions">
                <button className="pw-modal-btn" onClick={() => setShowNewFileModal(false)}>
                  Cancel
                </button>
                <button className="pw-modal-btn primary" onClick={createNewFile}>
                  Create
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Render: Main editor workspace ──
  return (
    <div className="pw-root bg-black min-h-screen text-white">
      {/* ── Top Bar ── */}
      <div className="pw-topbar">
        <div className="pw-topbar-left">
          <button
            onClick={() => {
              setActiveFileId(null);
              setShowTemplates(true);
            }}
            style={{ marginRight: 12, display: 'flex', alignItems: 'center', backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: '#888', transition: 'color 0.2s' }}
            title="Back"
          >
            <ArrowLeft size={18} />
          </button>
          <Link to="/" className="pw-topbar-logo">
            <img src="/DarkLogo.png" alt="MAIRA" className="h-20 w-auto object-contain block dark:hidden" />
            <img src="/Logo.png" alt="MAIRA" className="h-20 w-auto object-contain hidden dark:block" />
          </Link>
          {!sidebarCollapsed ? (
            <button
              className="pw-sidebar-icon-btn"
              onClick={() => setSidebarCollapsed(true)}
              title="Collapse sidebar"
            >
              <PanelLeftOpen size={16} />
            </button>
          ) : (
            <button
              className="pw-sidebar-icon-btn"
              onClick={() => setSidebarCollapsed(false)}
              title="Expand sidebar"
            >
              <PanelRightOpen size={16} />
            </button>
          )}
        </div>

        <div className="pw-topbar-right">
          {/* Layout menu */}
          <div style={{ position: 'relative' }}>
            <button
              className="pw-topbar-btn"
              onClick={() => setShowLayoutMenu(!showLayoutMenu)}
              title="Change layout"
            >
              <Layout size={14} />
              Layout
              <ChevronDown size={12} />
            </button>
            {showLayoutMenu && (
              <div className="pw-export-menu" style={{ minWidth: 200 }}>
                <div style={{ padding: '8px 12px', fontSize: 11, fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>
                  Workspace Layouts
                </div>
                <button
                  onClick={() => applyLayout('standard')}
                  style={{ height: 'auto', padding: '8px 12px', alignItems: 'flex-start', justifyContent: 'flex-start' }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-start' }}>
                    <span style={{ fontWeight: 500 }}>Standard (60:40)</span>
                    <span style={{ fontSize: 11, color: '#999', fontWeight: 400 }}>Balanced drafting</span>
                  </div>
                </button>
                <button
                  onClick={() => applyLayout('coding')}
                  style={{ height: 'auto', padding: '8px 12px', alignItems: 'flex-start', justifyContent: 'flex-start' }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-start' }}>
                    <span style={{ fontWeight: 500 }}>Deep Coding (75:25)</span>
                    <span style={{ fontSize: 11, color: '#999', fontWeight: 400 }}>Max editor space</span>
                  </div>
                </button>
                <button
                  onClick={() => applyLayout('review')}
                  style={{ height: 'auto', padding: '8px 12px', alignItems: 'flex-start', justifyContent: 'flex-start' }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-start' }}>
                    <span style={{ fontWeight: 500 }}>Proofread (30:70)</span>
                    <span style={{ fontSize: 11, color: '#999', fontWeight: 400 }}>Preview focused</span>
                  </div>
                </button>
              </div>
            )}
          </div>

          <button
            className="pw-topbar-btn"
            onClick={() => setPreviewCollapsed(!previewCollapsed)}
          >
            {previewCollapsed ? <Eye size={14} /> : <EyeOff size={14} />}
            {previewCollapsed ? 'Show Preview' : 'Hide Preview'}
          </button>

          {/* Export dropdown */}
          <div style={{ position: 'relative' }}>
            <button
              className="pw-topbar-btn pw-topbar-btn-primary"
              onClick={() => setShowExportMenu(!showExportMenu)}
            >
              <Download size={14} />
              Export
              <ChevronDown size={12} />
            </button>
            {showExportMenu && (
              <div className="pw-export-menu">
                <button onClick={() => exportFile('tex')}>
                  <FileText size={14} />
                  Download .tex
                </button>
                <button onClick={() => exportFile('copy')}>
                  <Copy size={14} />
                  Copy to clipboard
                </button>
                <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', margin: '4px 0' }} />
                <button onClick={() => exportFile('pdf')}>
                  <File size={14} />
                  Export to PDF
                </button>
                <button onClick={() => exportFile('doc')}>
                  <FileText size={14} />
                  Export to Word
                </button>
              </div>
            )}
          </div>

          <Link to="/" className="pw-topbar-btn">
            <ArrowLeft size={14} />
            Home
          </Link>
        </div>
      </div>

      {/* ── Workspace ── */}
      <div className="pw-workspace">
        {/* ── Left Sidebar ── */}
        <div
          className={`pw-sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}
          style={{ width: sidebarCollapsed ? 0 : sidebarWidth, flex: 'none' }}
        >
          {/* Sidebar Header */}
          <div className="pw-sidebar-header">
            <span className="pw-sidebar-header-title">Paper</span>
            <button
              className="pw-sidebar-icon-btn"
              onClick={() => setShowNewFileModal(true)}
              title="New file"
            >
              <Plus size={16} />
            </button>
            <button className="pw-sidebar-icon-btn" title="Search">
              <Search size={16} />
            </button>
          </div>

          {/* Tabs */}
          <div className="pw-sidebar-tabs">
            <button
              className={`pw-sidebar-tab ${sidebarTab === 'files' ? 'active' : ''}`}
              onClick={() => setSidebarTab('files')}
            >
              Files
            </button>
            <button
              className={`pw-sidebar-tab ${sidebarTab === 'chats' ? 'active' : ''}`}
              onClick={() => setSidebarTab('chats')}
            >
              Chat
            </button>
          </div>

          {/* Tab content */}
          {sidebarTab === 'files' ? (
            <>
              <div className="pw-file-tree">
                {files.map((f) => (
                  <div
                    key={f.id}
                    className={`pw-file-item ${f.id === activeFileId ? 'active' : ''}`}
                    onClick={() => {
                      setActiveFileId(f.id);
                      setShowTemplates(false);
                    }}
                  >
                    <File size={14} className="pw-file-icon" />
                    <span style={{ flex: 1 }}>{f.name}</span>
                    <button
                      className="pw-sidebar-icon-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        // Placeholder for plus action
                      }}
                      title="Add"
                      style={{ width: 22, height: 22, opacity: 0.6 }}
                    >
                      <Plus size={12} />
                    </button>
                    <button
                      className="pw-sidebar-icon-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteFile(f.id);
                      }}
                      title="Delete file"
                      style={{ width: 22, height: 22, opacity: 0.4 }}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                ))}
              </div>

              {/* Outline */}
              <div className="pw-outline-section">
                <div className="pw-outline-title" onClick={() => setOutlineOpen(!outlineOpen)}>
                  {outlineOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  Outline
                </div>
                {outlineOpen &&
                  outline.map((item, idx) => (
                    <div
                      key={idx}
                      className="pw-outline-item"
                      style={{ paddingLeft: 8 + item.level * 14, cursor: 'pointer' }}
                      onClick={() => scrollToLine(item.line)}
                    >
                      {item.label}
                    </div>
                  ))}
                {outlineOpen && outline.length === 0 && (
                  <div style={{ fontSize: 11, color: '#404040', padding: '4px 8px' }}>
                    No sections found
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, overflow: 'hidden' }}>
              <div className="pw-chat-messages">
                {chatMessages.length === 0 ? (
                  <div style={{ padding: '40px 20px', textAlign: 'center', color: '#737373', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <Sparkles size={24} style={{ marginBottom: 16, opacity: 0.4 }} />
                    <p style={{ fontSize: 13, lineHeight: '1.5', margin: 0 }}>
                      Ask me to draft sections, edit text, or format your paper.
                    </p>
                  </div>
                ) : (
                  chatMessages.map((msg) => (
                    <div key={msg.id} className={`pw-chat-msg ${msg.role}`}>
                      <div className="pw-chat-msg-text prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.text}
                        </ReactMarkdown>
                      </div>
                      {msg.role === 'ai' && msg.applied && msg.updatedLatex && (
                        <div className="pw-chat-msg-applied">
                          <Check size={12} />
                          Changes applied
                        </div>
                      )}
                    </div>
                  ))
                )}
                {aiThinking && (
                  <div className="pw-ai-thinking">
                    <div className="pw-ai-thinking-dot" />
                    <div className="pw-ai-thinking-dot" />
                    <div className="pw-ai-thinking-dot" />
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
              <div style={{ padding: 12, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                <div className="pw-ai-input-wrapper" style={{ padding: '6px 10px' }}>
                  <input
                    className="pw-ai-input"
                    placeholder="Ask AI..."
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendChatMessage();
                      }
                    }}
                  />
                  <button className="pw-sidebar-icon-btn" onClick={sendChatMessage}>
                    <Send size={14} />
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
        <div
          className={`pw-resize-handle ${resizing === 'sidebar' ? 'active' : ''}`}
          onMouseDown={() => setResizing('sidebar')}
        />

        {/* ── Editor Panel ── */}
        <div className="pw-editor-panel">
          {/* Editor Tabs */}
          <div className="pw-editor-tabs">
            {files.map((f) => (
              <div
                key={f.id}
                className={`pw-editor-tab ${f.id === activeFileId ? 'active' : ''}`}
                onClick={() => setActiveFileId(f.id)}
              >
                <FileText size={12} />
                {f.name}
                <span className="pw-editor-tab-close" onClick={(e) => { e.stopPropagation(); deleteFile(f.id); }}>
                  <X size={10} />
                </span>
              </div>
            ))}
            <button className="pw-editor-tools-btn" onClick={() => { setSidebarTab('chats'); setSidebarCollapsed(false); }}>
              <Wand2 size={12} />
              AI Tools
            </button>
          </div>

          {/* ── Formatting Toolbar ── */}
          {activeFile && (
            <div className="pw-toolbar">
              <button onClick={() => insertFormat('bold')} title="Bold">
                <Bold size={14} />
              </button>
              <button onClick={() => insertFormat('italic')} title="Italic">
                <Italic size={14} />
              </button>
              <button onClick={() => insertFormat('underline')} title="Underline">
                <Underline size={14} />
              </button>
              <div className="pw-toolbar-sep" />
              <button onClick={() => insertFormat('h1')} title="Section">
                <Heading1 size={14} />
              </button>
              <button onClick={() => insertFormat('h2')} title="Subsection">
                <Heading2 size={14} />
              </button>
              <div className="pw-toolbar-sep" />
              <button onClick={() => insertFormat('list')} title="List">
                <List size={14} />
              </button>
              <button onClick={() => insertFormat('quote')} title="Quote">
                <Quote size={14} />
              </button>
              <button onClick={() => insertFormat('code')} title="Code">
                <Code size={14} />
              </button>
              <div className="pw-toolbar-sep" />
              <button onClick={() => insertFormat('link')} title="Link">
                <LinkIcon size={14} />
              </button>
              <button onClick={() => insertFormat('image')} title="Image">
                <ImageIcon size={14} />
              </button>
              <button onClick={() => insertFormat('table')} title="Table">
                <Table size={14} />
              </button>
            </div>
          )}

          {/* Editor Body */}
          {activeFile ? (
            <div className="pw-editor-body" ref={editorContainerRef} />
          ) : (
            <div className="pw-empty-state">
              <div className="pw-empty-icon">
                <FileText size={28} />
              </div>
              <h3>No file open</h3>
              <p>Select a file from the sidebar or create a new one.</p>
              <button
                className="pw-topbar-btn pw-topbar-btn-primary"
                onClick={() => {
                  if (files.length === 0) setShowTemplates(true);
                }}
              >
                <Plus size={14} />
                New File
              </button>
            </div>
          )}

          {/* (AI Chat removed from bottom) */}
        </div>

        {/* ── Preview Panel ── */}
        {!previewCollapsed && (
          <>
            <div
              className={`pw-resize-handle ${resizing === 'preview' ? 'active' : ''}`}
              onMouseDown={() => setResizing('preview')}
            />
            <div
              className="pw-preview-panel"
              style={{ width: previewWidth, flex: 'none' }}
            >
              {/* Preview header */}
              <div className="pw-preview-header">
                <div className="pw-preview-header-left">
                  <div className={`pw-preview-status ${isCompiling ? 'compiling' : ''}`}>
                    {isCompiling ? (
                      <>
                        <div className="pw-compile-spinner" />
                        Compiling...
                      </>
                    ) : (
                      <>
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e' }} />
                        Compiled
                      </>
                    )}
                  </div>
                  <span className="pw-preview-page-info">Preview</span>
                </div>
                <div className="pw-preview-header-right">
                  {/* Zoom toggle removed - Default is Zoom to fit */}
                </div>
              </div>

              {/* Preview body - SCROLLABLE */}
              <div className="pw-preview-body" ref={previewBodyRef}>
                {activeFile ? (
                  <div
                    className="pw-preview-page"
                    dangerouslySetInnerHTML={{ __html: previewHtml }}
                    style={{ width: '100%', maxWidth: 'none' }}
                  />
                ) : (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flex: 1,
                      color: '#404040',
                      fontSize: 14,
                    }}
                  >
                    No document to preview
                  </div>
                )}
              </div>

              {/* Preview actions */}
              <div className="pw-preview-actions">
                <button
                  className="pw-preview-action-btn"
                  title="Refresh preview"
                  onClick={() => activeFile && setPreviewHtml(renderPreview(activeFile.content))}
                >
                  <RefreshCw size={16} />
                </button>
                <button className="pw-preview-action-btn" title="Previous page">
                  <ChevronLeft size={16} />
                </button>
                <button className="pw-preview-action-btn" title="Next page">
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ── Status Bar ── */}
      <div className="pw-statusbar">
        <div className="pw-statusbar-left">
          <div className="pw-statusbar-item">
            <div className="pw-statusbar-dot" />
            Connected
          </div>
        </div>
        <div className="pw-statusbar-right">
          {activeFile && (
            <span className="pw-statusbar-item">
              {activeFile.content.split('\n').length} lines
            </span>
          )}
          <span className="pw-statusbar-item">UTF-8</span>
          <span className="pw-statusbar-item">LaTeX</span>
        </div>
      </div>

      {/* ── New File Modal ── */}
      {
        showNewFileModal && (
          <div className="pw-modal-overlay" onClick={() => setShowNewFileModal(false)}>
            <div className="pw-modal" onClick={(e) => e.stopPropagation()}>
              <h3>Create New File</h3>
              <input
                className="pw-modal-input"
                placeholder="e.g. main.tex"
                value={newFileName}
                onChange={(e) => setNewFileName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && createNewFile()}
                autoFocus
              />
              <div className="pw-modal-actions">
                <button className="pw-modal-btn" onClick={() => setShowNewFileModal(false)}>
                  Cancel
                </button>
                <button className="pw-modal-btn primary" onClick={createNewFile}>
                  Create
                </button>
              </div>
            </div>
          </div>
        )
      }

      {/* Close menus on outside click */}
      {
        (showExportMenu || showLayoutMenu) && (
          <div
            style={{ position: 'fixed', inset: 0, zIndex: 29 }}
            onClick={() => { setShowExportMenu(false); setShowLayoutMenu(false); }}
          />
        )
      }
    </div >
  );
};