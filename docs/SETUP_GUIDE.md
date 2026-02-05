# Setup Guide

This guide covers the complete installation and configuration of the Exchange MCP Assistant, including all dependencies and their security considerations.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Security Model](#security-model)
3. [Dependency Overview](#dependency-overview)
4. [Installation Steps](#installation-steps)
5. [Configuration](#configuration)
6. [Verification](#verification)

---

## System Requirements

### Operating System
- **Windows 10/11** (tested) or Windows Server 2019+
- **Linux** (Ubuntu 20.04+, RHEL 8+) - should work but less tested
- **macOS** (12+) - should work but less tested

### Software Prerequisites

| Software | Version | Required | Purpose |
|----------|---------|----------|---------|
| Python | 3.11+ | Yes | Runtime environment |
| PowerShell | 7.0+ | Yes (Windows) | Startup scripts |
| Ollama | Latest | Yes* | Local LLM inference |
| Git | 2.0+ | Recommended | Version control |

*Ollama is required for local LLM mode. Alternative: OpenAI-compatible API.

### Hardware Recommendations

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Storage | 2 GB free | 10+ GB free |
| GPU | Not required | NVIDIA GPU for faster inference |

---

## Security Model

### Network Binding

**All services bind to localhost (127.0.0.1) only.** This is enforced at multiple levels:

1. **Environment default**: `HOST=127.0.0.1` in `.env.example`
2. **Code default**: `HOST: str = os.getenv("HOST", "127.0.0.1")` in server.py
3. **Startup script**: `$env:HOST = "127.0.0.1"` hardcoded in Start-App.ps1

**No services are exposed to the network by default.** To verify:

```powershell
# After starting the server, verify binding
netstat -an | findstr :8000
# Should show: TCP 127.0.0.1:8000 ... LISTENING
```

### Data Storage

- **Mock data**: Stored locally in `data/exchange_mcp.json`
- **Vector embeddings**: Stored locally in `data/chroma_db/`
- **No cloud storage**: All data remains on the local machine
- **No telemetry**: The application does not send data externally

### Authentication

> ⚠️ **Prototype Limitation**: The web interface currently has no user authentication. This is acceptable for localhost-only access but should be addressed before any network exposure.

### External Connections

The application makes outbound connections only when:

| Scenario | Destination | Purpose |
|----------|-------------|---------|
| Ollama (local) | `localhost:11434` | LLM inference |
| OpenAI API | `api.openai.com` | LLM inference (if configured) |
| Microsoft Graph | `graph.microsoft.com` | Email/calendar (if configured) |
| Exchange EWS | Your Exchange server | Email/calendar (if configured) |

---

## Dependency Overview

### Core Python Dependencies

#### mcp (Model Context Protocol)
- **Version**: ≥1.0.0
- **Source**: [PyPI](https://pypi.org/project/mcp/) | [GitHub](https://github.com/anthropics/anthropic-tools)
- **Purpose**: Implements the Model Context Protocol for tool-calling between LLMs and applications
- **Security Notes**: Developed by Anthropic; enables structured function calling
- **License**: MIT

#### chromadb
- **Version**: ≥0.4.24, <0.5.0
- **Source**: [PyPI](https://pypi.org/project/chromadb/) | [GitHub](https://github.com/chroma-core/chroma)
- **Purpose**: Vector database for semantic search over emails and meetings
- **Security Notes**: Runs entirely locally; no external connections; stores embeddings in SQLite
- **License**: Apache 2.0
- **Sub-dependencies**: 
  - `onnxruntime` - Neural network inference for embeddings
  - `sqlite3` - Local database storage

#### pydantic
- **Version**: ≥2.0.0
- **Source**: [PyPI](https://pypi.org/project/pydantic/) | [GitHub](https://github.com/pydantic/pydantic)
- **Purpose**: Data validation and settings management
- **Security Notes**: Widely used; no network access; validates data structures
- **License**: MIT

#### numpy
- **Version**: ≥1.24.0, <2.0.0
- **Source**: [PyPI](https://pypi.org/project/numpy/) | [GitHub](https://github.com/numpy/numpy)
- **Purpose**: Numerical operations for vector embeddings
- **Security Notes**: Core scientific computing library; no network access
- **License**: BSD-3-Clause

#### langchain / langchain-core
- **Version**: ≥0.3.0
- **Source**: [PyPI](https://pypi.org/project/langchain/) | [GitHub](https://github.com/langchain-ai/langchain)
- **Purpose**: LLM orchestration framework; manages prompts, tools, and agent logic
- **Security Notes**: Framework only; doesn't make network calls itself
- **License**: MIT

#### langchain-ollama
- **Version**: ≥0.2.0
- **Source**: [PyPI](https://pypi.org/project/langchain-ollama/)
- **Purpose**: LangChain integration for Ollama (local LLM)
- **Security Notes**: Connects to localhost Ollama instance only
- **License**: MIT

### Backend Server Dependencies

#### fastapi
- **Version**: Latest stable
- **Source**: [PyPI](https://pypi.org/project/fastapi/) | [GitHub](https://github.com/tiangolo/fastapi)
- **Purpose**: Modern async web framework for the REST API and WebSocket server
- **Security Notes**: Does not include authentication by default; binds to localhost
- **License**: MIT

#### uvicorn
- **Version**: Latest stable
- **Source**: [PyPI](https://pypi.org/project/uvicorn/) | [GitHub](https://github.com/encode/uvicorn)
- **Purpose**: ASGI server to run FastAPI application
- **Security Notes**: Bound to 127.0.0.1; no TLS by default (acceptable for localhost)
- **License**: BSD-3-Clause

#### python-dotenv
- **Version**: Latest stable
- **Source**: [PyPI](https://pypi.org/project/python-dotenv/)
- **Purpose**: Loads environment variables from `.env` file
- **Security Notes**: Local file access only; no network
- **License**: BSD-3-Clause

### Optional Dependencies

#### langchain-openai
- **Version**: Latest stable
- **Source**: [PyPI](https://pypi.org/project/langchain-openai/)
- **Purpose**: OpenAI API integration (for GPT models or compatible APIs)
- **Security Notes**: Makes HTTPS requests to configured API endpoint
- **License**: MIT
- **Required When**: Using `LLM_PROVIDER=openai`

#### msal / msgraph-sdk / azure-identity
- **Purpose**: Microsoft Graph API authentication and access
- **Security Notes**: OAuth2 authentication; requires Azure AD app registration
- **License**: MIT
- **Required When**: Using `DATA_SOURCE=graph`

#### exchangelib
- **Version**: Latest stable
- **Source**: [PyPI](https://pypi.org/project/exchangelib/)
- **Purpose**: Exchange Web Services (EWS) client
- **Security Notes**: Connects to configured Exchange server; supports NTLM/Basic auth
- **License**: BSD-2-Clause
- **Required When**: Using `DATA_SOURCE=ews`

### External Software

#### Ollama
- **Source**: [ollama.com](https://ollama.com/) | [GitHub](https://github.com/ollama/ollama)
- **Purpose**: Local LLM inference server; runs AI models on your machine
- **Security Notes**: 
  - Runs locally on port 11434
  - No data sent externally
  - Models downloaded from ollama.com registry
  - Open source (MIT license)
- **Required Models**: `llama3.2` (supports tool calling)

---

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/exchange-mcp.git
cd exchange-mcp
```

### 2. Create Python Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Activate (Linux/macOS)
source .venv/bin/activate
```

### 3. Install Python Dependencies

```bash
# Core dependencies
pip install -r exchange_mcp_server/requirements.txt

# Backend server dependencies
pip install fastapi uvicorn python-dotenv

# Optional: OpenAI-compatible providers
pip install langchain-openai

# Optional: Microsoft Graph API
pip install msal msgraph-sdk azure-identity

# Optional: Exchange Web Services
pip install exchangelib
```

### 4. Install Ollama

#### Windows
```powershell
# Download from https://ollama.com/download
# Or use winget:
winget install Ollama.Ollama
```

#### Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

#### macOS
```bash
brew install ollama
```

### 5. Pull Required Model

```bash
# Start Ollama service (if not running)
ollama serve

# Pull the model (in another terminal)
ollama pull llama3.2
```

### 6. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit as needed (default configuration works for mock data + Ollama)
```

### 7. Generate Sample Data

```powershell
# Generate mock Exchange data for testing
pwsh scripts/Generate-SingleUserData.ps1
```

---

## Configuration

See [Admin Guide](ADMIN_GUIDE.md) for detailed configuration options.

### Quick Configuration Reference

```bash
# .env file

# Server (always localhost)
HOST=127.0.0.1
PORT=8000

# LLM Provider
LLM_PROVIDER=ollama      # or "openai"
LLM_MODEL=llama3.2

# Data Source
DATA_SOURCE=mock         # or "graph" or "ews"

# Sync Interval
SYNC_INTERVAL_MINUTES=5
```

---

## Verification

### 1. Test Python Imports

```bash
python -c "from exchange_mcp_server import server; from backend.server import app; print('OK')"
```

### 2. Test Ollama Connection

```bash
curl http://localhost:11434/api/tags
# Should return list of available models
```

### 3. Start the Server

```powershell
.\Start-App.ps1 -SkipChecks
```

### 4. Verify Localhost Binding

```powershell
netstat -an | findstr :8000
# Should show: TCP 127.0.0.1:8000 ... LISTENING
```

### 5. Test the Interface

Open http://127.0.0.1:8000 in your browser.

---

## Troubleshooting

### Port Already in Use

```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Use different port
.\Start-App.ps1 -Port 8080
```

### Ollama Not Running

```bash
# Start Ollama service
ollama serve

# Check if running
curl http://localhost:11434/api/tags
```

### Model Not Found

```bash
# List available models
ollama list

# Pull required model
ollama pull llama3.2
```

### Import Errors

```bash
# Ensure virtual environment is activated
.\.venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r exchange_mcp_server/requirements.txt --force-reinstall
```

---

## Next Steps

- [User Guide](USER_GUIDE.md) - How to use the chat interface
- [Admin Guide](ADMIN_GUIDE.md) - Configuration and management
