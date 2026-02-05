# Exchange MCP Assistant

> ⚠️ **Prototype Notice**: This project is a proof-of-concept and is under active development. It is not production-ready and should be used for testing and evaluation purposes only.

> 🔒 **Security Note**: All services bind to `localhost` (127.0.0.1) only. No network services are exposed. See [Security Considerations](#-security) for details.

A personal AI assistant that connects to your Microsoft Exchange email and calendar data using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). Chat naturally with your inbox, search emails semantically, check your calendar, and find colleagues.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![Status](https://img.shields.io/badge/status-prototype-orange.svg)

## 📚 Documentation

| Guide | Description |
|-------|-------------|
| [Setup Guide](docs/SETUP_GUIDE.md) | Installation, dependencies, and security details |
| [User Guide](docs/USER_GUIDE.md) | How to use the chat interface |
| [Admin Guide](docs/ADMIN_GUIDE.md) | Configuration and management |
| [Developer Guide](docs/DEVELOPER_GUIDE.md) | Extending tools, actions, and data sources |

## ✨ Features

### Core Capabilities
- **Natural Language Chat** - Ask questions about your emails, meetings, and colleagues in plain English
- **Semantic Search** - Find emails and meetings by meaning, not just keywords (powered by ChromaDB)
- **Calendar Integration** - View upcoming meetings, today's schedule, and search past events
- **Colleague Directory** - Find people by name, email, or department
- **Real-time Sync** - Automatic background synchronization at configurable intervals

### Technical Features
- **Pluggable Data Sources** - Switch between mock data, Microsoft Graph API, or Exchange Web Services
- **Flexible LLM Providers** - Use local models via Ollama or any OpenAI-compatible API
- **Web-Based UI** - Modern dark-themed chat interface with status dashboard
- **MCP Protocol** - Built on the Model Context Protocol for tool-calling capabilities
- **Vector Search** - ChromaDB with ONNX embeddings for fast semantic retrieval

### Developer Features
- **Actions Framework** - Composable, testable workflows that sequence tool calls
- **Interaction Logging** - SQLite-based logging with full tool call traces
- **Feedback System** - Thumbs up/down on responses with dashboard for review
- **Feedback Dashboard** - Monitor approval rates, tool usage, and review negative feedback

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Browser)                        │
│                     HTML/CSS/JS Chat Interface                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP/WebSocket
┌─────────────────────────────▼───────────────────────────────────┐
│                    Backend (FastAPI Server)                      │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │ REST API    │  │ WebSocket    │  │ Background Sync Manager │ │
│  └──────┬──────┘  └──────┬───────┘  └────────────┬────────────┘ │
│         └────────────────┼───────────────────────┘              │
│                          ▼                                       │
│                  ┌───────────────┐                               │
│                  │  Chat Engine  │ ◄─── LangChain + LLM          │
│                  │  (ReAct Agent)│                               │
│                  └───────┬───────┘                               │
└──────────────────────────┼──────────────────────────────────────┘
                           │ Tool Calls
┌──────────────────────────▼──────────────────────────────────────┐
│                    MCP Server (exchange-mcp)                     │
│  ┌─────────────────────┐       ┌──────────────────────────────┐ │
│  │    Data Source      │       │      Vector Store            │ │
│  │  ┌───────────────┐  │       │       (ChromaDB)             │ │
│  │  │ Mock (JSON)   │  │       │  - Semantic email search     │ │
│  │  │ Graph API     │  │       │  - Semantic meeting search   │ │
│  │  │ EWS           │  │       │  - ONNX embeddings           │ │
│  │  └───────────────┘  │       └──────────────────────────────┘ │
│  └─────────────────────┘                                        │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Ollama** (for local LLM) - [Install Ollama](https://ollama.com/)
- **PowerShell 7+** (Windows) or bash (Linux/macOS)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/exchange-mcp.git
cd exchange-mcp

# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
# Or (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r exchange_mcp_server/requirements.txt
pip install fastapi uvicorn python-dotenv

# For OpenAI-compatible providers (optional)
pip install langchain-openai
```

### Generate Sample Data

```powershell
# Generate mock Exchange data for testing
pwsh scripts/Generate-SingleUserData.ps1
```

### Start the Server

```powershell
# Start the application (opens browser automatically)
.\Start-App.ps1

# Or with custom options
.\Start-App.ps1 -Mode dev -Port 8080

# Backend-only (no browser)
.\Start-App.ps1 -Mode backend
```

### Pull the Required Model

```bash
# The default model (required for tool calling)
ollama pull llama3.2
```

## ⚙️ Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

### LLM Provider

```bash
# Local Ollama (default)
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2

# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-your-api-key

# Other OpenAI-compatible (LM Studio, vLLM, etc.)
LLM_PROVIDER=openai
LLM_MODEL=your-model
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=not-needed
```

### Data Source

```bash
# Mock data (default - for testing)
DATA_SOURCE=mock

# Microsoft Graph API (Microsoft 365)
DATA_SOURCE=graph
GRAPH_TENANT_ID=your-tenant-id
GRAPH_CLIENT_ID=your-client-id
GRAPH_CLIENT_SECRET=your-secret
GRAPH_USER_EMAIL=user@company.com

# Exchange Web Services (on-premises)
DATA_SOURCE=ews
EWS_SERVER=mail.company.com
EWS_EMAIL=user@company.com
EWS_USERNAME=DOMAIN\\username
EWS_PASSWORD=your-password
```

## 📁 Project Structure

```
exchange-mcp/
├── backend/                    # FastAPI backend server
│   ├── server.py              # Main server with REST/WebSocket
│   ├── chat_engine.py         # LangChain agent with tools
│   └── __init__.py
├── frontend/                   # Web UI
│   ├── index.html             # Chat interface
│   ├── styles.css             # Dark theme styling
│   └── app.js                 # Client-side JavaScript
├── exchange_mcp_server/        # Core MCP server
│   ├── server.py              # MCP protocol implementation
│   ├── vector_store.py        # ChromaDB vector search
│   ├── data_sources/          # Pluggable data backends
│   │   ├── __init__.py        # Factory + base class
│   │   ├── mock_source.py     # JSON file source
│   │   ├── graph_source.py    # Microsoft Graph API
│   │   └── ews_source.py      # Exchange Web Services
│   └── requirements.txt
├── scripts/                    # Utility scripts
│   ├── Generate-SingleUserData.ps1
│   └── Update-IncrementalData.ps1
├── data/                       # Data storage (gitignored)
│   ├── exchange_mcp.json      # Mock data cache
│   └── chroma_db/             # Vector embeddings
├── Start-App.ps1              # Main startup script
├── .env.example               # Configuration template
└── README.md
```

## 🛠️ Available Tools

The AI assistant has access to these tools:

| Tool | Description |
|------|-------------|
| `whoami` | Get current user info |
| `get_inbox` | Retrieve inbox emails |
| `get_sent` | Retrieve sent emails |
| `read_email` | Read a specific email by ID |
| `search_emails` | Semantic search across emails |
| `get_calendar` | Get upcoming calendar events |
| `get_todays_meetings` | Get today's meetings |
| `search_meetings` | Semantic search across meetings |
| `find_colleague` | Search for a colleague |
| `list_colleagues` | List colleagues by department |
| `get_stats` | Get email/meeting statistics |

## 🔧 API Endpoints

### REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/status` | Server status with stats |
| POST | `/api/chat` | Send chat message |
| POST | `/api/sync` | Trigger data sync |
| GET | `/api/inbox` | Get inbox emails |
| GET | `/api/calendar` | Get calendar events |
| GET | `/api/meetings/today` | Get today's meetings |

### WebSocket

- `ws://localhost:8000/ws/chat` - Streaming chat interface

## 🔒 Security

### Network Isolation

**All services bind to localhost (127.0.0.1) only:**

- Server default: `HOST=127.0.0.1` (code and config)
- Startup script: Hardcoded `$env:HOST = "127.0.0.1"`
- No network exposure by default

**Verify with:**
```powershell
netstat -an | findstr :8000
# Should show: TCP 127.0.0.1:8000 ... LISTENING
```

### External Connections

| When | Destination | Purpose |
|------|-------------|---------|
| Always (Ollama mode) | `localhost:11434` | Local LLM |
| LLM_PROVIDER=openai | `api.openai.com` (or LLM_BASE_URL) | Cloud LLM |
| DATA_SOURCE=graph | `graph.microsoft.com` | Microsoft 365 |
| DATA_SOURCE=ews | Your Exchange server | On-prem Exchange |

### Not Implemented (Prototype)

- ❌ User authentication
- ❌ TLS/HTTPS
- ❌ Rate limiting
- ❌ Audit logging

See [Setup Guide](docs/SETUP_GUIDE.md) for complete security details.

## ⚠️ Known Limitations & Caveats

### Prototype Status
- **Not production-ready** - This is a proof-of-concept for demonstration purposes
- **Limited testing** - Edge cases and error handling may be incomplete
- **No authentication** - The web interface has no user authentication
- **Single user only** - Designed for personal use, not multi-tenant

### Technical Limitations
- **Model requirements** - Requires models that support tool/function calling (e.g., llama3.2, gpt-4)
- **Memory usage** - Vector indexing can be memory-intensive for large mailboxes
- **Initial indexing** - First run may take several minutes to index emails
- **Rate limits** - Graph API and EWS have rate limits that aren't fully handled

### Data Source Notes
- **Mock mode** - Uses generated fake data, not real emails
- **Graph API** - Requires Azure AD app registration and appropriate permissions
- **EWS mode** - Limited directory capabilities (no full AD access)

## 🗺️ Roadmap

Potential future enhancements:

- [ ] User authentication and authorization
- [ ] Email composition and sending
- [ ] Calendar event creation
- [ ] Attachment handling
- [ ] Message threading/conversation view
- [ ] Streaming responses in UI
- [ ] Multi-language support
- [ ] Docker containerization
- [ ] Comprehensive test suite
- [ ] Performance optimization for large mailboxes

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) - The protocol that makes tool calling possible
- [LangChain](https://www.langchain.com/) - LLM orchestration framework
- [Ollama](https://ollama.com/) - Local LLM inference
- [ChromaDB](https://www.trychroma.com/) - Vector database for semantic search
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework

---

**Disclaimer**: This project is not affiliated with or endorsed by Microsoft. Exchange, Microsoft 365, and related trademarks are property of Microsoft Corporation.
