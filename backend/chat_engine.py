#!/usr/bin/env python3
"""
Chat Engine for Exchange MCP Assistant.
Wraps LangChain functionality for use by the backend server.
Supports multiple LLM providers: Ollama (local) or OpenAI-compatible APIs.
"""

import json
import logging
import os
import warnings
from typing import Optional, Tuple, List

from langchain_core.tools import tool
from langchain_core.language_models.chat_models import BaseChatModel

# Suppress LangGraph deprecation warning
warnings.filterwarnings("ignore", message=".*create_react_agent.*")
from langgraph.prebuilt import create_react_agent

# Import MCP server components (initialized by backend.server)
from exchange_mcp_server import server as mcp_server

logger = logging.getLogger("exchange-backend.chat")


def create_llm(
    provider: str = "ollama",
    model: str = "llama3.2",
    api_key: str = "",
    base_url: str = "",
    temperature: float = 0
) -> BaseChatModel:
    """
    Create an LLM instance based on provider.
    
    Args:
        provider: "ollama" or "openai"
        model: Model name (e.g., "llama3.2", "gpt-4", "gpt-3.5-turbo")
        api_key: API key (required for openai provider)
        base_url: Custom base URL (for OpenAI-compatible APIs like LM Studio, vLLM, etc.)
        temperature: Sampling temperature (0 = deterministic)
    
    Returns:
        Configured LLM instance
    """
    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                "langchain-openai not installed. Run:\n"
                "  pip install langchain-openai"
            )
        
        kwargs = {
            "model": model,
            "temperature": temperature,
            "api_key": api_key,
        }
        
        # Custom base URL for OpenAI-compatible providers
        if base_url:
            kwargs["base_url"] = base_url
            
        return ChatOpenAI(**kwargs)
    
    else:  # ollama (default)
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model, temperature=temperature)


# ============================================================================
# Tool Definitions
# ============================================================================

def get_data_source():
    """Get the data loader (must be called after initialization)."""
    return mcp_server.data_source

def get_vector_store():
    """Get the vector store (must be called after initialization)."""
    return mcp_server.vector_store


@tool
def whoami() -> str:
    """Get information about the current user - name, email, department, unread emails, meetings today."""
    data_loader = get_data_source()
    me = data_loader.get_me()
    unread = data_loader.get_unread_count()
    today_meetings = len(data_loader.get_todays_meetings())
    
    return json.dumps({
        "name": me.get("DisplayName"),
        "email": me.get("Email"),
        "department": me.get("Department"),
        "title": me.get("JobTitle"),
        "unread_emails": unread,
        "meetings_today": today_meetings
    }, indent=2)


@tool
def get_inbox(limit: Optional[int] = 10, unread_only: Optional[bool] = False) -> str:
    """Get emails from my inbox.
    
    Args:
        limit: Maximum number of emails to return (default 10)
        unread_only: If True, only return unread emails (default False)
    """
    data_loader = get_data_source()
    
    if limit is None or isinstance(limit, dict):
        limit = 10
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 10
    if unread_only is None or isinstance(unread_only, dict):
        unread_only = False
        
    emails = data_loader.get_inbox(limit=limit, unread_only=unread_only)
    
    return json.dumps({
        "count": len(emails),
        "unread_total": data_loader.get_unread_count(),
        "emails": [
            {
                "id": e["Id"],
                "subject": e["Subject"],
                "from": e.get("FromName") or e["From"],
                "date": e["ReceivedDate"],
                "is_read": e.get("IsRead", False),
                "importance": e.get("Importance", "Normal"),
                "preview": e.get("Body", "")[:150] + "..." if len(e.get("Body", "")) > 150 else e.get("Body", "")
            }
            for e in emails
        ]
    }, indent=2)


@tool
def get_sent(limit: Optional[int] = 10) -> str:
    """Get emails I've sent.
    
    Args:
        limit: Maximum number of emails to return (default 10)
    """
    data_loader = get_data_source()
    
    if limit is None or isinstance(limit, dict):
        limit = 10
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 10
        
    emails = data_loader.get_sent_items(limit=limit)
    
    return json.dumps({
        "count": len(emails),
        "emails": [
            {
                "id": e["Id"],
                "subject": e["Subject"],
                "to": e.get("ToName") or e["To"],
                "date": e["ReceivedDate"],
                "preview": e.get("Body", "")[:100]
            }
            for e in emails
        ]
    }, indent=2)


@tool
def read_email(email_id: Optional[str] = None) -> str:
    """Read the full content of a specific email by its ID.
    
    Args:
        email_id: The email ID to read
    """
    data_loader = get_data_source()
    
    if email_id is None or isinstance(email_id, dict):
        return json.dumps({"error": "Please provide an email_id"})
        
    email = data_loader.get_email_by_id(str(email_id))
    if email:
        return json.dumps({
            "id": email["Id"],
            "subject": email["Subject"],
            "from": email.get("FromName") or email["From"],
            "to": email.get("ToName") or email["To"],
            "date": email["ReceivedDate"],
            "body": email["Body"],
            "importance": email.get("Importance", "Normal"),
            "has_attachments": email.get("HasAttachments", False)
        }, indent=2)
    return json.dumps({"error": f"Email not found: {email_id}"})


@tool
def search_emails(query: Optional[str] = None, limit: Optional[int] = 10) -> str:
    """Search my emails using natural language. Examples: 'emails about pipeline failures', 'messages from the data team about Spark'.
    
    Args:
        query: Natural language search query
        limit: Maximum results (default 10)
    """
    vector_store = get_vector_store()
    
    if query is None or isinstance(query, dict):
        return json.dumps({"error": "Please provide a search query"})
    query = str(query)
    if limit is None or isinstance(limit, dict):
        limit = 10
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 10
        
    results = vector_store.search_emails(query, limit=limit)
    
    return json.dumps({
        "query": query,
        "count": len(results),
        "results": results
    }, indent=2)


@tool
def get_calendar(days: Optional[int] = 7) -> str:
    """Get my upcoming meetings for the next N days.
    
    Args:
        days: Number of days to look ahead (default 7)
    """
    data_loader = get_data_source()
    
    if days is None or isinstance(days, dict):
        days = 7
    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 7
        
    meetings = data_loader.get_calendar(days=days)
    
    return json.dumps({
        "days_ahead": days,
        "count": len(meetings),
        "meetings": [
            {
                "id": m["Id"],
                "subject": m["Subject"],
                "organizer": m.get("OrganizerName") or m["Organizer"],
                "start": m["StartTime"],
                "end": m["EndTime"],
                "location": m.get("Location", "")
            }
            for m in meetings
        ]
    }, indent=2)


@tool
def get_todays_meetings() -> str:
    """Get all meetings scheduled for today."""
    data_loader = get_data_source()
    meetings = data_loader.get_todays_meetings()
    
    return json.dumps({
        "count": len(meetings),
        "meetings": [
            {
                "id": m["Id"],
                "subject": m["Subject"],
                "start": m["StartTime"],
                "end": m["EndTime"],
                "location": m.get("Location", ""),
                "organizer": m.get("OrganizerName") or m["Organizer"]
            }
            for m in meetings
        ]
    }, indent=2)


@tool
def search_meetings(query: Optional[str] = None, limit: Optional[int] = 10) -> str:
    """Search my meetings using natural language. Examples: 'architecture reviews', '1:1 meetings', 'sprint planning'.
    
    Args:
        query: Natural language search query
        limit: Maximum results (default 10)
    """
    vector_store = get_vector_store()
    
    if query is None or isinstance(query, dict):
        return json.dumps({"error": "Please provide a search query"})
    query = str(query)
    if limit is None or isinstance(limit, dict):
        limit = 10
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 10
        
    results = vector_store.search_meetings(query, limit=limit)
    
    return json.dumps({
        "query": query,
        "count": len(results),
        "results": results
    }, indent=2)


@tool
def find_colleague(query: Optional[str] = None) -> str:
    """Find a colleague by name, email, or department.
    
    Args:
        query: Name, email, or department to search for
    """
    data_loader = get_data_source()
    
    if query is None or isinstance(query, dict):
        return json.dumps({"error": "Please provide a search query"})
    query = str(query)
    
    colleagues = data_loader.search_colleagues(query)
    
    return json.dumps({
        "query": query,
        "count": len(colleagues),
        "colleagues": [
            {
                "name": c["DisplayName"],
                "email": c["Email"],
                "department": c["Department"],
                "title": c["JobTitle"],
                "phone": c.get("Phone", "N/A")
            }
            for c in colleagues
        ]
    }, indent=2)


@tool
def list_colleagues(department: Optional[str] = None, limit: Optional[int] = 20) -> str:
    """List colleagues, optionally filtered by department.
    
    Args:
        department: Filter by department name (optional)
        limit: Maximum results (default 20)
    """
    data_loader = get_data_source()
    
    if isinstance(department, dict):
        department = None
    if limit is None or isinstance(limit, dict):
        limit = 20
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 20
        
    colleagues = data_loader.get_colleagues(department=department, limit=limit)
    
    return json.dumps({
        "filter": department or "all",
        "count": len(colleagues),
        "colleagues": [
            {
                "name": c["DisplayName"],
                "email": c["Email"],
                "department": c["Department"],
                "title": c["JobTitle"]
            }
            for c in colleagues
        ]
    }, indent=2)


@tool
def get_stats() -> str:
    """Get email and meeting statistics - inbox count, unread count, top senders, meeting counts."""
    data_loader = get_data_source()
    email_stats = data_loader.get_email_stats()
    meeting_stats = data_loader.get_meeting_stats()
    
    return json.dumps({
        "email": email_stats,
        "meetings": meeting_stats
    }, indent=2)


# All available tools
TOOLS = [
    whoami,
    get_inbox,
    get_sent,
    read_email,
    search_emails,
    get_calendar,
    get_todays_meetings,
    search_meetings,
    find_colleague,
    list_colleagues,
    get_stats
]


# ============================================================================
# Chat Engine Class
# ============================================================================

class ChatEngine:
    """Chat engine using LangChain with configurable LLM provider."""
    
    def __init__(
        self,
        model: str = "llama3.2",
        provider: str = "ollama",
        api_key: str = "",
        base_url: str = ""
    ):
        """
        Initialize the chat engine.
        
        Args:
            model: Model name (e.g., "llama3.2", "gpt-4o", "gpt-3.5-turbo")
            provider: LLM provider - "ollama" or "openai"
            api_key: API key (required for openai provider)
            base_url: Custom base URL for OpenAI-compatible APIs
        """
        self.model_name = model
        self.provider = provider
        self.tools_used_in_last_call: List[str] = []
        
        # Initialize LLM based on provider
        base_llm = create_llm(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0
        )
        
        # Build system prompt
        data_loader = get_data_source()
        me = data_loader.get_me()
        
        self.system_prompt = f"""You are a helpful personal assistant with access to the user's Exchange email and calendar data.

IMPORTANT: You MUST use the available tools to answer questions about emails, meetings, or colleagues.
NEVER make up or hallucinate data - always call the appropriate tool first.

Available tools:
- whoami: Get your user info
- get_inbox: Get inbox emails  
- get_sent: Get sent emails
- read_email: Read a specific email by ID
- search_emails: Search emails with natural language
- get_calendar: Get upcoming meetings
- get_todays_meetings: Get today's meetings
- search_meetings: Search meetings with natural language
- find_colleague: Find a colleague
- list_colleagues: List colleagues by department
- get_stats: Get email/meeting statistics

The user is: {me.get('DisplayName', 'Unknown')} ({me.get('Email', 'Unknown')}) from {me.get('Department', 'Unknown')}.

When responding:
- ALWAYS call a tool first to get real data
- Summarize the tool results clearly
- Be concise but informative
- Highlight important/urgent items"""

        # Bind tools to the LLM
        self.llm = base_llm.bind_tools(TOOLS)
        
        # Create the agent
        self.agent = create_react_agent(self.llm, TOOLS, prompt=self.system_prompt)
        
        provider_info = f"{provider}:{model}"
        if base_url:
            provider_info += f" @ {base_url}"
        logger.info(f"ChatEngine initialized with {provider_info}")
    
    def chat(self, message: str) -> Tuple[str, List[str]]:
        """
        Send a message and get a response.
        
        Returns:
            Tuple of (response_text, list_of_tools_used)
        """
        self.tools_used_in_last_call = []
        
        result = self.agent.invoke({"messages": [("user", message)]})
        
        # Track which tools were used
        tools_used = []
        if result and "messages" in result:
            for msg in result["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if isinstance(tc, dict) and "name" in tc:
                            tools_used.append(tc["name"])
        
        self.tools_used_in_last_call = tools_used
        
        # Extract the final AI response
        response = "I couldn't process that request."
        if result and "messages" in result:
            for msg in reversed(result["messages"]):
                # Skip tool call messages
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    continue
                # Get content from AI message
                if hasattr(msg, "content") and msg.content:
                    content = msg.content
                    # Skip if it's just echoing the user message
                    if content.strip() == message.strip():
                        continue
                    response = content
                    break
        
        return response, tools_used
