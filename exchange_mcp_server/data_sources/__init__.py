"""
Data Source Abstraction Layer for Exchange MCP

Provides a common interface for data sources, allowing easy switching between:
- MockDataSource: Reads from local JSON file (current behavior)
- GraphDataSource: Connects to Microsoft Graph API (Exchange Online + Azure AD)
- EWSDataSource: Connects to Exchange Web Services (on-prem Exchange)

Usage:
    from exchange_mcp_server.data_sources import create_data_source
    
    # Mock mode (default)
    source = create_data_source("mock")
    
    # Microsoft Graph API mode
    source = create_data_source("graph", tenant_id="...", client_id="...", client_secret="...")
    
    # Exchange Web Services mode
    source = create_data_source("ews", server="exchange.company.com", username="...", password="...")
"""

from abc import ABC, abstractmethod
from typing import Any
from datetime import datetime


class DataSourceBase(ABC):
    """Abstract base class for all data sources."""
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the data source connection."""
        pass
    
    @abstractmethod
    def reload(self) -> None:
        """Refresh data from the source."""
        pass
    
    # =========================================================================
    # User / Identity
    # =========================================================================
    
    @abstractmethod
    def get_me(self) -> dict:
        """Get the current user's profile."""
        pass
    
    @abstractmethod
    def get_my_email(self) -> str:
        """Get the current user's email address."""
        pass
    
    # =========================================================================
    # Colleagues / Directory
    # =========================================================================
    
    @abstractmethod
    def get_colleagues(self, department: str | None = None, limit: int = 20) -> list[dict]:
        """Get colleagues, optionally filtered by department."""
        pass
    
    @abstractmethod
    def search_colleagues(self, query: str, limit: int = 10) -> list[dict]:
        """Search colleagues by name, email, or department."""
        pass
    
    @abstractmethod
    def get_org_structure(self) -> dict:
        """Get organization structure grouped by department."""
        pass
    
    # =========================================================================
    # Emails
    # =========================================================================
    
    @abstractmethod
    def get_all_emails(self) -> list[dict]:
        """Get all emails (for indexing)."""
        pass
    
    @abstractmethod
    def get_email_by_id(self, email_id: str) -> dict | None:
        """Get a specific email by ID."""
        pass
    
    @abstractmethod
    def get_inbox(self, limit: int = 20, unread_only: bool = False) -> list[dict]:
        """Get inbox emails."""
        pass
    
    @abstractmethod
    def get_sent_items(self, limit: int = 20) -> list[dict]:
        """Get sent emails."""
        pass
    
    @abstractmethod
    def get_unread_count(self) -> int:
        """Get count of unread emails."""
        pass
    
    # =========================================================================
    # Calendar / Meetings
    # =========================================================================
    
    @abstractmethod
    def get_all_meetings(self) -> list[dict]:
        """Get all meetings (for indexing)."""
        pass
    
    @abstractmethod
    def get_meeting_by_id(self, meeting_id: str) -> dict | None:
        """Get a specific meeting by ID."""
        pass
    
    @abstractmethod
    def get_calendar(self, days: int = 7, include_past: bool = False) -> list[dict]:
        """Get calendar events for the specified period."""
        pass
    
    @abstractmethod
    def get_todays_meetings(self) -> list[dict]:
        """Get today's meetings."""
        pass
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    @abstractmethod
    def get_email_stats(self) -> dict:
        """Get email statistics."""
        pass
    
    @abstractmethod
    def get_meeting_stats(self) -> dict:
        """Get meeting statistics."""
        pass


def create_data_source(
    source_type: str = "mock",
    **kwargs
) -> DataSourceBase:
    """
    Factory function to create the appropriate data source.
    
    Args:
        source_type: One of "mock", "graph", or "ews"
        **kwargs: Source-specific configuration
        
    Returns:
        Configured DataSourceBase instance
        
    Examples:
        # Mock mode (reads from JSON)
        source = create_data_source("mock", cache_path="data/exchange_mcp.json")
        
        # Microsoft Graph API
        source = create_data_source(
            "graph",
            tenant_id="your-tenant-id",
            client_id="your-app-id",
            client_secret="your-secret"
        )
        
        # Exchange Web Services
        source = create_data_source(
            "ews",
            server="mail.company.com",
            email="user@company.com",
            password="..."
        )
    """
    if source_type == "mock":
        from exchange_mcp_server.data_sources.mock_source import MockDataSource
        return MockDataSource(**kwargs)
    
    elif source_type == "graph":
        from exchange_mcp_server.data_sources.graph_source import GraphDataSource
        return GraphDataSource(**kwargs)
    
    elif source_type == "ews":
        from exchange_mcp_server.data_sources.ews_source import EWSDataSource
        return EWSDataSource(**kwargs)
    
    else:
        raise ValueError(f"Unknown data source type: {source_type}. Use 'mock', 'graph', or 'ews'")
