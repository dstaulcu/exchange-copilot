# Admin Guide

This guide covers configuration, management, and troubleshooting for administrators deploying the Exchange MCP Assistant.

## Table of Contents

1. [Configuration Reference](#configuration-reference)
2. [Data Sources](#data-sources)
3. [LLM Providers](#llm-providers)
4. [Security Considerations](#security-considerations)
5. [Monitoring & Logging](#monitoring--logging)
6. [Data Management](#data-management)
7. [Troubleshooting](#troubleshooting)
8. [Performance Tuning](#performance-tuning)

---

## Configuration Reference

All configuration is done via environment variables, typically set in a `.env` file.

### Server Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `127.0.0.1` | **Do not change** - Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `false` | Enable debug mode (auto-reload, verbose logs) |

> ⚠️ **Security**: The HOST variable is hardcoded to `127.0.0.1` in the startup script. Do not expose this service to the network without implementing proper authentication.

### LLM Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | LLM provider: `ollama` or `openai` |
| `LLM_MODEL` | `llama3.2` | Model name |
| `LLM_API_KEY` | (empty) | API key (required for openai provider) |
| `LLM_BASE_URL` | (empty) | Custom API endpoint URL |
| `OLLAMA_MODEL` | (deprecated) | Legacy alias for LLM_MODEL |

### Data Source Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_SOURCE` | `mock` | Data source: `mock`, `graph`, or `ews` |
| `DATA_PATH` | `data` | Base directory for all data storage |
| `DATA_FILE` | `data/exchange_mcp.json` | Path to mock data file |
| `CHROMA_DB_PATH` | `data/chroma_db` | Path to ChromaDB vector store |
| `SYNC_INTERVAL_MINUTES` | `5` | Auto-sync interval |

> **Path Configuration**: `DATA_PATH` is the base directory. `DATA_FILE` and `CHROMA_DB_PATH` can be absolute or relative paths. If relative, they default to subdirectories of `DATA_PATH`.

### Microsoft Graph Settings

| Variable | Required | Description |
|----------|----------|-------------|
| `GRAPH_TENANT_ID` | Yes | Azure AD tenant ID |
| `GRAPH_CLIENT_ID` | Yes | Application (client) ID |
| `GRAPH_CLIENT_SECRET` | Yes | Client secret |
| `GRAPH_USER_EMAIL` | Yes | User email to access |

### Exchange Web Services Settings

| Variable | Required | Description |
|----------|----------|-------------|
| `EWS_SERVER` | No* | Exchange server hostname |
| `EWS_EMAIL` | Yes | User email address |
| `EWS_USERNAME` | Yes | Login username (DOMAIN\\user or email) |
| `EWS_PASSWORD` | Yes | User password |
| `EWS_AUTODISCOVER` | No | Use autodiscover (default: true) |

*Required if `EWS_AUTODISCOVER=false`

---

## Data Sources

### Mock Data Source

For testing and demonstration. Uses pre-generated JSON data.

```bash
DATA_SOURCE=mock
DATA_PATH=data
DATA_FILE=data/exchange_mcp.json
CHROMA_DB_PATH=data/chroma_db
```

**Generate mock data:**
```powershell
pwsh scripts/Generate-SingleUserData.ps1
```

**Add incremental data:**
```powershell
pwsh scripts/Update-IncrementalData.ps1
```

### Microsoft Graph API

For Microsoft 365 / Exchange Online environments.

#### Azure AD App Registration

1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App Registrations
2. Click "New registration"
3. Name: "Exchange MCP Assistant"
4. Supported account types: "Single tenant"
5. Redirect URI: Leave blank (not needed for daemon app)
6. Click "Register"

#### API Permissions

Add these **Application** permissions:

| Permission | Type | Purpose |
|------------|------|---------|
| `User.Read.All` | Application | Read user directory |
| `Mail.Read` | Application | Read emails |
| `Calendars.Read` | Application | Read calendar |

Then click "Grant admin consent for [tenant]"

#### Client Secret

1. Go to "Certificates & secrets"
2. Click "New client secret"
3. Copy the secret value immediately (shown only once)

#### Configuration

```bash
DATA_SOURCE=graph
GRAPH_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
GRAPH_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
GRAPH_CLIENT_SECRET=your-secret-value
GRAPH_USER_EMAIL=user@company.com
```

#### Dependencies

```bash
pip install msal msgraph-sdk azure-identity
```

### Exchange Web Services

For on-premises Exchange or hybrid environments.

```bash
DATA_SOURCE=ews
EWS_EMAIL=user@company.com
EWS_USERNAME=DOMAIN\\username
EWS_PASSWORD=secure-password
EWS_AUTODISCOVER=true

# Or with explicit server:
EWS_AUTODISCOVER=false
EWS_SERVER=mail.company.com
```

#### Dependencies

```bash
pip install exchangelib
```

#### Notes

- EWS has limited directory capabilities (no full AD access)
- For full directory search, consider LDAP integration (not implemented)
- Self-signed certificates may require additional configuration

---

## LLM Providers

### Ollama (Local)

Recommended for privacy and offline use.

```bash
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2
```

**Supported models** (must support tool calling):
- `llama3.2` (recommended, 3B params)
- `llama3.2:1b` (smaller, faster)
- `llama3.1:8b` (larger, more capable)
- `mistral` (may hallucinate more)

**Start Ollama:**
```bash
ollama serve
ollama pull llama3.2
```

### OpenAI

For cloud-based inference.

```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-your-api-key
```

**Supported models:**
- `gpt-4o` (recommended)
- `gpt-4-turbo`
- `gpt-3.5-turbo`

### OpenAI-Compatible APIs

Works with any OpenAI-compatible endpoint.

```bash
LLM_PROVIDER=openai
LLM_MODEL=your-model-name
LLM_API_KEY=your-api-key
LLM_BASE_URL=http://your-server/v1
```

**Examples:**

| Provider | LLM_BASE_URL |
|----------|--------------|
| LM Studio | `http://localhost:1234/v1` |
| vLLM | `http://localhost:8000/v1` |
| Together.ai | `https://api.together.xyz/v1` |
| Ollama (OpenAI mode) | `http://localhost:11434/v1` |

---

## Security Considerations

### Network Security

1. **Localhost Only**: All services bind to `127.0.0.1`
   - Enforced in code defaults
   - Hardcoded in startup script
   - Verify: `netstat -an | findstr :8000`

2. **No TLS**: HTTP only (acceptable for localhost)
   - Do not expose to network without TLS termination
   - Use reverse proxy (nginx, traefik) if network access needed

3. **No Authentication**: Web interface has no auth
   - Acceptable for localhost single-user
   - Implement auth before any network exposure

### Credential Management

1. **Environment Variables**: Use `.env` file (gitignored)
2. **Never commit**: API keys, passwords, secrets
3. **Rotate regularly**: Especially client secrets

### Data Protection

1. **Local storage**: All data in `data/` directory
2. **No cloud sync**: Data stays on local machine
3. **Vector embeddings**: Text is converted to vectors, not stored verbatim

### Audit Considerations

For security review, note these external connections:

| Component | Connection | Configurable |
|-----------|-----------|--------------|
| Ollama | localhost:11434 | No (local only) |
| OpenAI API | api.openai.com | Yes (LLM_BASE_URL) |
| Microsoft Graph | graph.microsoft.com | No |
| Exchange EWS | Your server | Yes (EWS_SERVER) |

---

## Monitoring & Logging

### Log Output

Logs are written to stdout. Capture with:

```powershell
.\Start-App.ps1 2>&1 | Tee-Object -FilePath server.log
```

### Log Levels

Set via `DEBUG` environment variable:

- `DEBUG=false`: INFO level (default)
- `DEBUG=true`: DEBUG level (verbose)

### Health Check

```bash
curl http://127.0.0.1:8000/api/health
# {"status": "healthy", "timestamp": "..."}
```

### Status Endpoint

```bash
curl http://127.0.0.1:8000/api/status
# {"user": {...}, "sync": {...}, "uptime": ...}
```

### Sync Status

The `/api/status` endpoint includes sync information:

```json
{
  "sync": {
    "last_sync": "2026-02-05T10:30:00",
    "sync_count": 12,
    "interval_minutes": 5,
    "is_running": true
  }
}
```

---

## Data Management

### Regenerating Mock Data

```powershell
# Delete existing data
Remove-Item data\exchange_mcp.json -Force
Remove-Item data\chroma_db -Recurse -Force

# Generate fresh data
pwsh scripts\Generate-SingleUserData.ps1

# Restart server to reindex
```

### Clearing Vector Index

```powershell
# Stop server first
Remove-Item data\chroma_db -Recurse -Force

# Restart server (will reindex automatically)
```

### Manual Sync

```bash
# Via API
curl -X POST http://127.0.0.1:8000/api/sync

# Via UI
# Click "Sync" button in sidebar
```

### Backup

```powershell
# Backup data
Copy-Item data\exchange_mcp.json data\backup\

# Backup vectors (optional, can be regenerated)
Copy-Item data\chroma_db data\backup\ -Recurse
```

---

## Troubleshooting

### Server Won't Start

**Port in use:**
```powershell
netstat -ano | findstr :8000
# Kill process or use different port:
.\Start-App.ps1 -Port 8080
```

**Import errors:**
```powershell
# Ensure venv is active
.\.venv\Scripts\Activate.ps1

# Check imports
python -c "from backend.server import app; print('OK')"
```

### Ollama Issues

**Connection refused:**
```bash
# Start Ollama
ollama serve
```

**Model not found:**
```bash
ollama pull llama3.2
```

**Slow responses:**
- First query loads model into memory
- Check available RAM
- Try smaller model: `llama3.2:1b`

### Data Source Issues

**Mock data not found:**
```powershell
pwsh scripts\Generate-SingleUserData.ps1
```

**Graph API errors:**
- Verify app registration permissions
- Check admin consent granted
- Validate tenant/client IDs

**EWS authentication failed:**
- Verify credentials
- Check server hostname
- Test with explicit server (disable autodiscover)

### Vector Search Issues

**No search results:**
- Data may not be indexed
- Restart server to reindex
- Check `data/chroma_db/` exists

**Slow indexing:**
- First run indexes all documents
- Subsequent starts skip indexed docs
- Large mailboxes may take minutes

---

## Performance Tuning

### Reduce Memory Usage

1. Use smaller model: `LLM_MODEL=llama3.2:1b`
2. Limit indexed emails (configure data source)
3. Clear vector cache periodically

### Improve Response Time

1. Use faster model (smaller)
2. Use GPU with Ollama
3. Pre-warm model: `ollama run llama3.2 "test"`

### Scale Considerations

This is a **single-user prototype**. For multi-user:

- Implement user authentication
- Use per-user vector stores
- Consider cloud LLM for scalability
- Add rate limiting
- Implement proper session management

---

## Startup Script Options

```powershell
.\Start-App.ps1 [options]

Options:
  -Mode <string>       Run mode: full, backend, dev (default: full)
  -Port <int>          Server port (default: 8000)
  -Model <string>      LLM model name (default: llama3.2)
  -SyncInterval <int>  Sync interval in minutes (default: 5)
  -SkipChecks          Skip Ollama and data checks

Examples:
  .\Start-App.ps1                           # Full app with browser
  .\Start-App.ps1 -Mode backend             # API only
  .\Start-App.ps1 -Mode dev -Port 8080      # Dev mode on port 8080
  .\Start-App.ps1 -SkipChecks               # Fast startup
```

---

## Related Documentation

- [Setup Guide](SETUP_GUIDE.md) - Installation instructions
- [User Guide](USER_GUIDE.md) - End-user documentation
- [README](../README.md) - Project overview
