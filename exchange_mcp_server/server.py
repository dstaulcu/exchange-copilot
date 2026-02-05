#!/usr/bin/env python3
"""
Exchange MCP Server (Single-User Mode)
A Model Context Protocol server for personal Exchange/AD data with semantic search.
"""

import json
import logging
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from exchange_mcp_server.data_sources import create_data_source, DataSourceBase
from exchange_mcp_server.vector_store import VectorStore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("exchange-mcp")

# Initialize MCP server
server = Server("exchange-mcp")

# Global instances
# Data source can be: mock (JSON file), graph (Microsoft 365), or ews (Exchange Server)
data_source: DataSourceBase | None = None
vector_store: VectorStore | None = None


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def initialize(source_type: str = "mock", chroma_db_path: str | None = None, **source_config):
    """
    Initialize data source and vector store.
    
    Args:
        source_type: One of "mock", "graph", or "ews"
        chroma_db_path: Path to ChromaDB storage (defaults to data/chroma_db)
        **source_config: Configuration for the data source
        
    Examples:
        # Mock mode (default)
        initialize("mock")
        
        # Microsoft Graph API
        initialize("graph", tenant_id="...", client_id="...", client_secret="...", user_email="...")
        
        # Exchange Web Services
        initialize("ews", email="...", username="...", password="...", server="...")
    """
    global data_source, vector_store
    
    # Use provided path or fall back to environment variable or default
    import os
    if chroma_db_path is None:
        default_data_path = str(get_project_root() / "data")
        data_path = os.getenv("DATA_PATH", default_data_path)
        chroma_db_path = os.getenv("CHROMA_DB_PATH", os.path.join(data_path, "chroma_db"))
    
    chroma_path = Path(chroma_db_path)
    
    # Create data source based on type
    if source_type == "mock" and "cache_path" not in source_config:
        default_data_path = str(get_project_root() / "data")
        data_path = os.getenv("DATA_PATH", default_data_path)
        source_config["cache_path"] = os.getenv("DATA_FILE", os.path.join(data_path, "exchange_mcp.json"))
    
    logger.info(f"Initializing data source: {source_type}")
    data_source = create_data_source(source_type, **source_config)
    data_source.initialize()
    
    me = data_source.get_me()
    logger.info(f"Loaded data for: {me.get('DisplayName', 'Unknown')} <{me.get('Email', 'Unknown')}>")
    
    logger.info(f"Initializing vector store at {chroma_path}")
    vector_store = VectorStore(str(chroma_path))
    
    # Index emails and meetings if not already indexed
    if vector_store.needs_indexing():
        logger.info("Indexing emails and meetings...")
        emails = data_source.get_all_emails()
        meetings = data_source.get_all_meetings()
        vector_store.index_documents(emails, meetings)
        logger.info(f"Indexed {len(emails)} emails and {len(meetings)} meetings")


def sync_data() -> dict:
    """Reload data from source and index any new documents.
    For mock mode, call after running Update-IncrementalData.ps1.
    For live sources (graph/ews), fetches latest data from server."""
    global data_source, vector_store
    
    # Reload data from source
    data_source.reload()
    
    # Index only new documents
    emails = data_source.get_all_emails()
    meetings = data_source.get_all_meetings()
    
    result = vector_store.index_new_documents(emails, meetings)
    logger.info(f"Sync complete: {result}")
    
    return result

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """List available MCP tools."""
    return [
        types.Tool(
            name="whoami",
            description="Get information about the current user (me)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="get_inbox",
            description="Get emails from my inbox",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of emails to return",
                        "default": 10
                    },
                    "unread_only": {
                        "type": "boolean",
                        "description": "Only return unread emails",
                        "default": False
                    }
                }
            }
        ),
        types.Tool(
            name="get_sent",
            description="Get emails I've sent",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of emails to return",
                        "default": 10
                    }
                }
            }
        ),
        types.Tool(
            name="read_email",
            description="Read a specific email by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The email ID"
                    }
                },
                "required": ["email_id"]
            }
        ),
        types.Tool(
            name="search_emails",
            description="Search my emails using natural language (semantic search)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search (e.g., 'emails about pipeline failures', 'messages about Spark optimization')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_calendar",
            description="Get my upcoming meetings",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Days ahead to look",
                        "default": 7
                    }
                }
            }
        ),
        types.Tool(
            name="get_todays_meetings",
            description="Get today's meetings",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="get_meeting",
            description="Get details of a specific meeting",
            inputSchema={
                "type": "object",
                "properties": {
                    "meeting_id": {
                        "type": "string",
                        "description": "The meeting ID"
                    }
                },
                "required": ["meeting_id"]
            }
        ),
        types.Tool(
            name="search_meetings",
            description="Search my meetings using natural language (semantic search)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search (e.g., 'architecture reviews', '1:1 meetings')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="find_colleague",
            description="Find a colleague by name, email, or department",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Name, email, or department to search"
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="list_colleagues",
            description="List colleagues, optionally filtered by department",
            inputSchema={
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "description": "Filter by department (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results",
                        "default": 20
                    }
                }
            }
        ),
        types.Tool(
            name="get_org_structure",
            description="Get the organization structure by department",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="get_stats",
            description="Get email and meeting statistics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="sync",
            description="Sync data - reload from cache and index any new emails/meetings",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="find_similar_emails",
            description="Find emails similar to a given email",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "Email ID to find similar emails for"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum similar emails",
                        "default": 5
                    }
                },
                "required": ["email_id"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Handle tool calls."""
    try:
        if name == "whoami":
            me = data_source.get_me()
            unread = data_source.get_unread_count()
            today_meetings = len(data_source.get_todays_meetings())
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "name": me.get("DisplayName"),
                    "email": me.get("Email"),
                    "department": me.get("Department"),
                    "title": me.get("JobTitle"),
                    "phone": me.get("Phone", "N/A"),
                    "office": me.get("Office", "N/A"),
                    "unread_emails": unread,
                    "meetings_today": today_meetings
                }, indent=2)
            )]
        
        elif name == "get_inbox":
            limit = arguments.get("limit", 10)
            unread_only = arguments.get("unread_only", False)
            emails = data_source.get_inbox(limit=limit, unread_only=unread_only)
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "count": len(emails),
                    "unread_total": data_source.get_unread_count(),
                    "emails": [
                        {
                            "id": e["Id"],
                            "subject": e["Subject"],
                            "from": e.get("FromName") or e["From"],
                            "date": e["ReceivedDate"],
                            "is_read": e.get("IsRead", False),
                            "importance": e.get("Importance", "Normal"),
                            "preview": e.get("Body", "")[:100] + "..." if len(e.get("Body", "")) > 100 else e.get("Body", "")
                        }
                        for e in emails
                    ]
                }, indent=2)
            )]
        
        elif name == "get_sent":
            limit = arguments.get("limit", 10)
            emails = data_source.get_sent_items(limit=limit)
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "count": len(emails),
                    "emails": [
                        {
                            "id": e["Id"],
                            "subject": e["Subject"],
                            "to": e.get("ToName") or e["To"],
                            "date": e["ReceivedDate"],
                            "preview": e.get("Body", "")[:100] + "..." if len(e.get("Body", "")) > 100 else e.get("Body", "")
                        }
                        for e in emails
                    ]
                }, indent=2)
            )]
        
        elif name == "read_email":
            email_id = arguments.get("email_id")
            email = data_source.get_email_by_id(email_id)
            if email:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "id": email["Id"],
                        "subject": email["Subject"],
                        "from": email.get("FromName") or email["From"],
                        "to": email.get("ToName") or email["To"],
                        "date": email["ReceivedDate"],
                        "body": email["Body"],
                        "is_read": email.get("IsRead", False),
                        "importance": email.get("Importance", "Normal"),
                        "has_attachments": email.get("HasAttachments", False),
                        "folder": email.get("FolderPath", "Unknown")
                    }, indent=2)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Email not found: {email_id}"})
                )]
        
        elif name == "search_emails":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 10)
            results = vector_store.search_emails(query, limit=limit)
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "query": query,
                    "count": len(results),
                    "results": results
                }, indent=2)
            )]
        
        elif name == "get_calendar":
            days = arguments.get("days", 7)
            meetings = data_source.get_calendar(days=days)
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "days_ahead": days,
                    "count": len(meetings),
                    "meetings": [
                        {
                            "id": m["Id"],
                            "subject": m["Subject"],
                            "organizer": m.get("OrganizerName") or m["Organizer"],
                            "start": m["StartTime"],
                            "end": m["EndTime"],
                            "location": m.get("Location", ""),
                            "attendees": m.get("Attendees", "")
                        }
                        for m in meetings
                    ]
                }, indent=2)
            )]
        
        elif name == "get_todays_meetings":
            meetings = data_source.get_todays_meetings()
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
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
            )]
        
        elif name == "get_meeting":
            meeting_id = arguments.get("meeting_id")
            meeting = data_source.get_meeting_by_id(meeting_id)
            if meeting:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        "id": meeting["Id"],
                        "subject": meeting["Subject"],
                        "organizer": meeting.get("OrganizerName") or meeting["Organizer"],
                        "attendees": meeting.get("Attendees", ""),
                        "start": meeting["StartTime"],
                        "end": meeting["EndTime"],
                        "location": meeting.get("Location", ""),
                        "body": meeting.get("Body", ""),
                        "is_recurring": meeting.get("IsRecurring", False)
                    }, indent=2)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Meeting not found: {meeting_id}"})
                )]
        
        elif name == "search_meetings":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 10)
            results = vector_store.search_meetings(query, limit=limit)
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "query": query,
                    "count": len(results),
                    "results": results
                }, indent=2)
            )]
        
        elif name == "find_colleague":
            query = arguments.get("query", "")
            colleagues = data_source.search_colleagues(query)
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "query": query,
                    "count": len(colleagues),
                    "colleagues": [
                        {
                            "name": c["DisplayName"],
                            "email": c["Email"],
                            "department": c["Department"],
                            "title": c["JobTitle"],
                            "phone": c.get("Phone", "N/A"),
                            "office": c.get("Office", "N/A")
                        }
                        for c in colleagues
                    ]
                }, indent=2)
            )]
        
        elif name == "list_colleagues":
            department = arguments.get("department")
            limit = arguments.get("limit", 20)
            colleagues = data_source.get_colleagues(department=department, limit=limit)
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
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
            )]
        
        elif name == "get_org_structure":
            org = data_source.get_org_structure()
            return [types.TextContent(
                type="text",
                text=json.dumps(org, indent=2)
            )]
        
        elif name == "get_stats":
            email_stats = data_source.get_email_stats()
            meeting_stats = data_source.get_meeting_stats()
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "email": email_stats,
                    "meetings": meeting_stats
                }, indent=2)
            )]
        
        elif name == "sync":
            result = sync_data()
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "status": "success",
                    "message": "Data synced successfully",
                    **result
                }, indent=2)
            )]
        
        elif name == "find_similar_emails":
            email_id = arguments.get("email_id")
            limit = arguments.get("limit", 5)
            
            email = data_source.get_email_by_id(email_id)
            if not email:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Email not found: {email_id}"})
                )]
            
            query = f"{email['Subject']} {email.get('Body', '')}"
            results = vector_store.search_emails(query, limit=limit + 1)
            results = [r for r in results if r.get("id") != email_id][:limit]
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    "original": email["Subject"],
                    "similar": results
                }, indent=2)
            )]
        
        else:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"})
            )]
    
    except Exception as e:
        logger.exception(f"Error in tool {name}")
        return [types.TextContent(
            type="text",
            text=json.dumps({"error": str(e)})
        )]


async def main():
    """Main entry point."""
    initialize()
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
