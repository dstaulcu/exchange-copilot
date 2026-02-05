# Developer Guide

This guide explains how to extend the Exchange MCP Assistant with new tools, actions, and workflows.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                           │
│                    (Chat + Feedback UI)                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                      Backend Server                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Chat Engine │  │   Actions   │  │   Interaction Logger    │  │
│  │ (LangChain) │  │  Framework  │  │   (SQLite + Feedback)   │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
│         │                │                     │                 │
│         └────────────────┼─────────────────────┘                 │
│                          │                                       │
└──────────────────────────┼───────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                        Tool Layer                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  Email   │  │ Calendar │  │  Search  │  │   Colleagues     │ │
│  │  Tools   │  │  Tools   │  │  Tools   │  │     Tools        │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘ │
│       │             │             │                 │            │
└───────┼─────────────┼─────────────┼─────────────────┼────────────┘
        │             │             │                 │
┌───────▼─────────────▼─────────────▼─────────────────▼────────────┐
│                      Data Source Layer                          │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │   Mock   │  │   MS Graph   │  │    Exchange Web Services  │  │
│  │  (JSON)  │  │     API      │  │           (EWS)           │  │
│  └──────────┘  └──────────────┘  └───────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Adding New Tools

Tools are individual functions the LLM can call. They're defined in `backend/chat_engine.py`.

### Step 1: Define the Tool Function

```python
from langchain_core.tools import tool

@tool
def my_new_tool(param1: str, param2: int = 10) -> str:
    """
    Clear description of what this tool does.
    The LLM uses this docstring to decide when to call the tool.
    
    Args:
        param1: Description of parameter 1
        param2: Description of parameter 2 (default: 10)
    """
    # Implementation
    data_source = get_data_source()
    
    # Do something with the data source
    result = data_source.some_method(param1, param2)
    
    # Return JSON for structured data
    return json.dumps({
        "status": "success",
        "data": result
    }, indent=2)
```

### Step 2: Register the Tool

Add your tool to the `TOOLS` list in `chat_engine.py`:

```python
TOOLS = [
    whoami,
    get_inbox,
    # ... existing tools ...
    my_new_tool,  # Add here
]
```

### Step 3: Test the Tool

```python
# In Python REPL or test file
from backend.chat_engine import my_new_tool

# Call directly (tools are just functions)
result = my_new_tool("test", 5)
print(result)
```

### Tool Best Practices

1. **Clear Docstrings**: The LLM uses docstrings to understand when to call tools
2. **Return JSON**: Structured output helps the LLM interpret results
3. **Handle Errors**: Return error messages in JSON rather than raising exceptions
4. **Validate Inputs**: Tools may receive unexpected types; validate and provide defaults
5. **Be Specific**: One tool should do one thing well

---

## Actions Framework

Actions are composable workflows that sequence multiple tool calls. They provide:

- **Reusability**: Define once, execute anywhere
- **Testability**: Test complex workflows in isolation
- **Traceability**: Full execution traces for debugging

### Creating an Action

Actions are defined in `backend/actions/definitions.py`.

```python
from backend.actions.base import Action, ActionContext, ActionResult, registry

@registry.register
class MyCustomAction(Action):
    """Docstring explaining what this action does."""
    
    # Metadata
    name = "my_custom_action"
    description = "Short description for display"
    tags = ["email", "search"]  # For categorization
    
    def execute(self, context: ActionContext) -> ActionResult:
        """
        Main execution logic.
        
        Args:
            context: Contains user_query, session info, and variables
            
        Returns:
            ActionResult with output or error
        """
        # Access context variables
        search_term = context.get("search_term")
        if not search_term:
            return self.fail("search_term required")
        
        # Step 1: Call a tool
        inbox = self.call_tool("get_inbox", limit=20, unread_only=True)
        
        # Step 2: Process results
        matching_emails = [
            e for e in inbox.get("emails", [])
            if search_term.lower() in e.get("subject", "").lower()
        ]
        
        # Step 3: Maybe call more tools
        if matching_emails:
            first_email = self.call_tool(
                "read_email", 
                email_id=matching_emails[0]["id"]
            )
            context.set("first_match", first_email)
        
        # Return success with output
        return self.complete(output={
            "search_term": search_term,
            "matches": len(matching_emails),
            "emails": matching_emails
        })
```

### Action Lifecycle

```
1. Action.run(context)       # Entry point
   ├─ Reset internal state
   ├─ Start timer
   │
2. Action.execute(context)   # Your implementation
   ├─ call_tool("tool1")     # Records call + result
   ├─ call_tool("tool2")     # Records call + result
   ├─ ...
   │
3. Return ActionResult
   ├─ status: success/failed/partial
   ├─ output: your result data
   ├─ tool_calls: full trace of all calls
   └─ duration_ms: execution time
```

### Testing Actions

```python
import pytest
from backend.actions.base import ActionContext
from backend.actions.definitions import MyCustomAction

class TestMyCustomAction:
    """Test suite for MyCustomAction."""
    
    def test_success_case(self):
        """Test successful execution."""
        # Create mock tools
        mock_tools = {
            "get_inbox": lambda **kwargs: {
                "emails": [
                    {"id": "1", "subject": "Test Subject"},
                    {"id": "2", "subject": "Another Email"},
                ]
            },
            "read_email": lambda **kwargs: {
                "id": kwargs["email_id"],
                "body": "Email content"
            }
        }
        
        # Create action with mock tools
        action = MyCustomAction(tool_registry=mock_tools)
        
        # Create context
        context = ActionContext(
            user_query="Find test emails",
            model_name="test",
            provider="test"
        )
        context.set("search_term", "Test")
        
        # Execute
        result = action.run(context)
        
        # Assert
        assert result.status.value == "success"
        assert result.output["matches"] == 1
        assert len(result.tool_calls) == 2
    
    def test_missing_required_param(self):
        """Test failure when required param is missing."""
        action = MyCustomAction(tool_registry={})
        context = ActionContext(
            user_query="Find emails",
            model_name="test",
            provider="test"
        )
        # Don't set search_term
        
        result = action.run(context)
        
        assert result.status.value == "failed"
        assert "search_term required" in result.error
```

### Using Actions from Chat

Actions can be triggered from the chat engine or exposed as tools:

```python
from backend.actions import ActionContext, REGISTERED_ACTIONS

# Execute an action
context = ActionContext(
    user_query="Get my daily summary",
    model_name="llama3.2",
    provider="ollama"
)

result = REGISTERED_ACTIONS.execute("daily_summary", context)
print(result.output)
```

### Available Actions

| Action | Description | Tags |
|--------|-------------|------|
| `daily_summary` | Quick summary of emails and meetings | email, calendar, summary |
| `daily_briefing` | **Printable meeting intelligence** for today's meetings | calendar, email, prep, briefing |
| `get_email_thread` | Full email thread for a given email | email, search |
| `meeting_prep` | Background info for a specific meeting | calendar, email, lookup |
| `colleague_lookup` | Colleague details with recent interactions | lookup, email, calendar |
| `inbox_triage` | Categorized inbox by priority | email, summary |

### Daily Briefing Action

The `daily_briefing` action is designed for **informed meeting participation**:

**What it does:**
1. Gets today's calendar with all meetings
2. For each meeting, identifies key topics from subject/body
3. Searches recent emails (inbox + sent) for relevant conversations
4. Identifies key collaborators based on email frequency
5. Compiles a formatted, printable briefing document

**Output structure:**
```python
{
    "date": "2026-02-05",
    "user": "Alice Smith",
    "meetings_count": 3,
    "briefings": [
        {
            "meeting": {
                "subject": "Q1 Planning Review",
                "time": "10:00 AM",
                "organizer": "Bob Johnson",
                "attendees": ["Alice Smith", "Carol Davis"],
                "location": "Conference Room B"
            },
            "agenda_keywords": ["planning", "budget", "roadmap"],
            "key_collaborators": [
                {"name": "Bob Johnson", "email_count": 5},
                {"name": "Carol Davis", "email_count": 3}
            ],
            "related_findings": [
                {
                    "subject": "Re: Q1 Budget Numbers",
                    "from": "Bob Johnson",
                    "date": "2026-02-04",
                    "preview": "Updated numbers attached..."
                }
            ]
        }
    ],
    "print_ready": "...formatted text for printing..."
}
```

**Quick Action:** Available via "Daily Briefing" button in the UI sidebar.

---

## Interaction Logging & Feedback

All chat interactions are automatically logged to `data/interactions.db`.

### Log Structure

```
InteractionLog
├── interaction_id: unique ID
├── session_id: groups related messages
├── timestamp: when it occurred
├── user_query: what the user asked
├── response: what the assistant said
├── tool_calls: list of ToolCallLog
│   ├── tool_name
│   ├── arguments
│   ├── result
│   ├── error (if any)
│   └── duration_ms
├── model_provider: "ollama" or "openai"
├── model_name: e.g., "llama3.2"
├── total_duration_ms: end-to-end time
├── feedback_rating: 1 (up), -1 (down), 0, or null
├── feedback_comment: optional text
└── feedback_categories: optional list ["speed", "quality", "accuracy"]
```

### Feedback Categories

Users can optionally categorize their feedback:

| Category | Description |
|----------|-------------|
| `speed` | Response time was too slow or appropriately fast |
| `quality` | Response quality, formatting, completeness |
| `accuracy` | Correctness of the information provided |

The UI shows an expandable feedback form after the initial thumbs up/down:
1. User clicks 👍 or 👎 (quick feedback)
2. Optionally, they can expand to select categories and add a comment
3. If no action after 5 seconds, basic rating is auto-submitted

### Accessing Logs

```python
from backend.interaction_log import get_interaction_store

store = get_interaction_store()

# Get recent interactions
recent = store.get_recent(limit=50)

# Get feedback statistics (includes category counts)
stats = store.get_feedback_stats()
print(f"Approval rate: {stats['approval_rate']}%")
print(f"Speed issues: {stats['category_counts']['speed']}")

# Get interactions needing review
negative = store.get_negative_feedback(limit=20)

# Export for analysis
store.export_to_json("interactions_export.json")
```

### Feedback Dashboard

Access the feedback dashboard at: `http://localhost:8000/dashboard.html`

Features:
- Aggregate statistics (total interactions, approval rate)
- **Feedback category breakdown** (speed, quality, accuracy counts)
- Tool usage metrics (call counts, error rates)
- Negative feedback review queue
- Recent interactions timeline with category badges

---

## Data Source Abstraction

Data sources implement the `DataSourceBase` interface in `exchange_mcp_server/data_sources/`.

### Interface

```python
from abc import ABC, abstractmethod

class DataSourceBase(ABC):
    """Base class for all data sources."""
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize connection/load data."""
        pass
    
    @abstractmethod
    def reload(self) -> None:
        """Refresh data from source."""
        pass
    
    @abstractmethod
    def get_me(self) -> dict:
        """Get current user info."""
        pass
    
    @abstractmethod
    def get_inbox(self, limit: int = 20, unread_only: bool = False) -> list[dict]:
        """Get inbox emails."""
        pass
    
    # ... more methods
```

### Creating a New Data Source

1. Create `exchange_mcp_server/data_sources/my_source.py`:

```python
from exchange_mcp_server.data_sources import DataSourceBase

class MyCustomSource(DataSourceBase):
    """Data source for MySystem."""
    
    def __init__(self, api_key: str, endpoint: str):
        self.api_key = api_key
        self.endpoint = endpoint
        self.client = None
    
    def initialize(self) -> None:
        self.client = MySystemClient(self.api_key, self.endpoint)
        self.client.connect()
    
    def get_me(self) -> dict:
        user = self.client.get_current_user()
        return {
            "Id": user.id,
            "Email": user.email,
            "DisplayName": user.name,
            # ... map to expected format
        }
    
    # Implement all abstract methods...
```

2. Register in `exchange_mcp_server/data_sources/__init__.py`:

```python
def create_data_source(source_type: str, **config) -> DataSourceBase:
    if source_type == "mock":
        from .mock_source import MockDataSource
        return MockDataSource(**config)
    elif source_type == "my_source":
        from .my_source import MyCustomSource
        return MyCustomSource(**config)
    # ...
```

3. Add configuration to `.env.example`:

```bash
# --- MySystem Mode (DATA_SOURCE=my_source) ---
# MY_SOURCE_API_KEY=your-api-key
# MY_SOURCE_ENDPOINT=https://api.mysystem.com
```

---

## LLM Provider Abstraction

LLM providers are configured via the `create_llm()` factory in `backend/chat_engine.py`.

### Adding a New Provider

```python
def create_llm(provider: str, model: str, **kwargs) -> BaseChatModel:
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model, temperature=0)
    
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, **kwargs)
    
    elif provider == "anthropic":
        # New provider
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, **kwargs)
    
    else:
        raise ValueError(f"Unknown provider: {provider}")
```

---

## Configuration Reference

All configuration flows through environment variables:

```
.env file
    │
    ▼
os.getenv()
    │
    ▼
backend/server.py: Config class
    │
    ├──► LLM Provider (create_llm)
    ├──► Data Source (create_data_source)
    └──► Vector Store (VectorStore)
```

### Adding New Config Options

1. Add to `Config` class in `backend/server.py`:

```python
class Config:
    # Existing...
    
    # New setting
    MY_SETTING: str = os.getenv("MY_SETTING", "default_value")
```

2. Document in `.env.example`:

```bash
# My Setting
# Description of what it does
MY_SETTING=default_value
```

3. Update `docs/ADMIN_GUIDE.md` with the new setting.

---

## Testing

### Unit Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_actions.py

# Run with coverage
pytest --cov=backend --cov-report=html
```

### Integration Tests

```python
# tests/test_integration.py
import pytest
from fastapi.testclient import TestClient
from backend.server import app

@pytest.fixture
def client():
    return TestClient(app)

def test_chat_endpoint(client):
    response = client.post("/api/chat", json={
        "message": "What's in my inbox?"
    })
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "tools_used" in data
```

### Mock Data for Testing

The mock data source can be used for testing without real Exchange access:

```python
from exchange_mcp_server.data_sources import create_data_source

# Create mock source with custom data
source = create_data_source("mock", cache_path="tests/fixtures/test_data.json")
source.initialize()

# Use in tests
emails = source.get_inbox(limit=5)
```

---

## Debugging

### Enable Debug Mode

```bash
DEBUG=true python -m backend.server
```

This enables:
- Auto-reload on code changes
- Verbose logging
- Detailed error messages

### Inspect Tool Calls

View tool calls in the feedback dashboard or query directly:

```python
from backend.interaction_log import get_interaction_store

store = get_interaction_store()
interaction = store.get_interaction("abc123")

for tc in interaction.tool_calls:
    print(f"{tc.tool_name}: {tc.duration_ms}ms")
    if tc.error:
        print(f"  ERROR: {tc.error}")
```

### Common Issues

1. **Tool not being called**: Check the docstring - LLM uses it for tool selection
2. **Wrong tool parameters**: Add input validation with clear error messages
3. **Slow responses**: Check tool durations in the dashboard
4. **LLM hallucinating**: Strengthen system prompt, add "NEVER make up data" instructions

---

## Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes with tests
3. Run tests: `pytest`
4. Update documentation
5. Submit pull request

### Code Style

- Python: Follow PEP 8
- TypeScript/JS: Use Prettier
- Docstrings: Google style
- Commit messages: Conventional commits
