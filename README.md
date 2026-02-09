# MAIRA (Multi-Agent Intelligent Research Assistant for Automated Report Generation)– Deep Research Agent

MAIRA is a sophisticated AI-powered research platform that combines multiple specialized agents to perform deep research, analysis, and reporting. The system features a modern React-based chat interface and a powerful FastAPI backend with intelligent task routing.

## 🌟 Features

### Intelligent Multi-Tier System
- **Tier 1 (Conversational)**: Handles greetings and simple social interactions
- **Tier 2 (Informational)**: Quick searches for facts, news, and simple data queries
- **Tier 3 (Analytical)**: Deep research with multi-agent orchestration for complex questions

### Specialized Sub-Agents
- **Web Search Agent**: Conducts deep web research and extracts webpage content
- **Academic Paper Agent**: Retrieves peer-reviewed papers from arXiv
- **Draft Agent**: Creates structured research drafts
- **Report Agent**: Generates comprehensive reports from research findings

### Export Capabilities
- PDF report generation
- DOCX document export
- Formatted research outputs

### Modern Chat Interface
- Thread-based conversations with UUID v7
- Real-time streaming responses
- Speech recognition support
- Markdown rendering with syntax highlighting
- Responsive design with Tailwind CSS

## 🏗️ Architecture

```
agent/
├── backend/           # FastAPI server and agent logic
│   ├── main.py       # API endpoints and server configuration
│   ├── main_agent.py # Core orchestration agent
│   ├── config.py     # Model configuration (Gemini, Groq)
│   ├── thread_manager.py # Thread/conversation management
│   ├── *_agent.py    # Specialized sub-agents
│   └── tools/        # Agent tools (search, PDF, arXiv, etc.)
└── frontend/         # React + TypeScript UI
    └── MAIRA/
        ├── src/      # React components and logic
        └── public/   # Static assets
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+**
- **Node.js 18+** and npm
- **API Keys**:
  - Google Gemini API key
  - Groq API key (optional)
  - Other service API keys as required by tools

### Backend Setup

1. Navigate to the backend directory:
```bash
cd agent/backend
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the backend directory with your API keys:
```bash
# Copy the example environment file
cp .env.example .env

# Then edit .env and fill in your actual API keys
```

Required API keys (see `backend/.env.example` for full list):
- `GOOGLE_API_KEY` - Google Gemini API key
- `TAVILY_API_KEY` - Tavily search API key
- `LANGCHAIN_API_KEY` - LangChain/LangSmith API key (optional, for tracing)
- `GROQ_API_KEY` - Groq API key (optional, for alternative models)
- `ANTHROPIC_API_KEY` - Anthropic API key (optional, for Claude models)

⚠️ **Security Note**: Never commit your `.env` file with real API keys!

5. Start the FastAPI server:
```bash
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd agent/frontend/MAIRA
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The UI will be available at `http://localhost:5173` (or the port shown in terminal)

## 📡 API Endpoints

### Thread Management
- `POST /threads` - Create a new conversation thread
- `GET /threads` - List all threads
- `GET /threads/{thread_id}` - Get thread details
- `PATCH /threads/{thread_id}` - Update thread title
- `DELETE /threads/{thread_id}` - Delete a thread

### Agent Interaction
- `POST /agent/stream` - Stream agent responses (SSE)
- `POST /agent/invoke` - Get complete agent response

### Request Format
```json
{
  "prompt": "Your research question",
  "thread_id": "optional-thread-id",
  "deep_research": false
}
```

Set `deep_research: true` to enable Tier 3 (deep research with all sub-agents).

## 🛠️ Technologies Used

### Backend
- **FastAPI** - High-performance API framework
- **LangChain** - LLM orchestration
- **DeepAgents** - Multi-agent framework
- **Google Gemini** - Primary LLM (gemini-3-pro-preview)
- **Groq** - Alternative LLM provider
- **LangGraph** - Agent workflow management

### Frontend
- **React 19** - UI library
- **TypeScript** - Type-safe JavaScript
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Utility-first styling
- **Axios** - HTTP client
- **React Markdown** - Markdown rendering
- **Lucide React** - Icon library

## 🔧 Configuration

### Model Selection
Edit [config.py](agent/backend/config.py) to change the LLM model:

```python
# Current: Gemini 3 Pro
model = ChatGoogleGenerativeAI(model="models/gemini-3-pro-preview", temperature=0)

# Alternative options available in config.py
```

### Agent Behavior
Modify agent prompts and behavior in:
- [main_agent.py](agent/backend/main_agent.py) - Main orchestration logic
- Individual `*_agent.py` files for sub-agent customization

## 📝 Usage Examples

### Quick Information Query (Tier 2)
```
User: What is the current price of Bitcoin?
Mode: CHAT
Response: Immediate web search result
```

### Deep Research (Tier 3)
```
User: Analyze the impact of quantum computing on cryptography
Mode: DEEP_RESEARCH
Response: 
1. Web research on latest developments
2. Academic papers from arXiv
3. Comprehensive analysis and synthesis
4. Formatted report output
```

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is available for personal and educational use.

## 🙏 Acknowledgments

- Built with [DeepAgents](https://github.com/deepagents/deepagents) framework
- Powered by Google Gemini and other LLM providers
- UI components inspired by modern chat interfaces

## 📞 Support

For issues, questions, or suggestions, please open an issue in the repository.

---

**Note**: Make sure to keep your API keys secure and never commit them to version control. Always use environment variables for sensitive configuration.
