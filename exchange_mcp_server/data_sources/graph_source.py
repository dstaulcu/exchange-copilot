"""
Microsoft Graph API Data Source

Connects to Microsoft 365 / Exchange Online via Microsoft Graph API.
Requires Azure AD app registration with appropriate permissions.

Required permissions (delegated or application):
- User.Read (get current user)
- User.Read.All (search directory)
- Mail.Read (read emails)
- Calendars.Read (read calendar)

Setup:
1. Register an app in Azure AD (portal.azure.com)
2. Add the required API permissions
3. Create a client secret or configure certificate auth
4. Note your tenant_id, client_id, and client_secret

Install dependencies:
    pip install msal msgraph-sdk

Usage:
    source = GraphDataSource(
        tenant_id="your-tenant-id",
        client_id="your-app-client-id", 
        client_secret="your-client-secret",
        # For delegated auth, also provide:
        # user_email="user@company.com"
    )
    source.initialize()
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from exchange_mcp_server.data_sources import DataSourceBase

logger = logging.getLogger("exchange-mcp.graph")


class GraphDataSource(DataSourceBase):
    """
    Data source using Microsoft Graph API.
    
    This implementation uses the Microsoft Graph SDK to fetch data from
    Microsoft 365 services (Exchange Online, Azure AD).
    """
    
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str | None = None,
        user_email: str | None = None,
        use_delegated_auth: bool = False,
    ):
        """
        Initialize Graph API data source.
        
        Args:
            tenant_id: Azure AD tenant ID
            client_id: Application (client) ID from Azure AD app registration
            client_secret: Client secret for app-only auth
            user_email: User email for delegated auth scenarios
            use_delegated_auth: Whether to use delegated (user) auth vs app-only
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_email = user_email
        self.use_delegated_auth = use_delegated_auth
        
        self._client = None
        self._me: dict = {}
        
    def initialize(self) -> None:
        """Initialize the Graph API client."""
        try:
            # Check for required dependencies
            import msal
            from msgraph import GraphServiceClient
            from azure.identity import ClientSecretCredential
        except ImportError as e:
            raise ImportError(
                "Microsoft Graph SDK not installed. Run:\n"
                "  pip install msal msgraph-sdk azure-identity"
            ) from e
        
        logger.info("Initializing Microsoft Graph API connection...")
        
        # Create credential
        credential = ClientSecretCredential(
            tenant_id=self.tenant_id,
            client_id=self.client_id,
            client_secret=self.client_secret
        )
        
        # Create Graph client
        scopes = ['https://graph.microsoft.com/.default']
        self._client = GraphServiceClient(credentials=credential, scopes=scopes)
        
        # Fetch current user info
        self._fetch_me()
        
        logger.info(f"Connected as: {self._me.get('displayName')} <{self._me.get('mail')}>")
    
    def _fetch_me(self) -> None:
        """Fetch current user profile from Graph API."""
        import asyncio
        
        async def get_me():
            if self.user_email:
                # Delegated or specific user
                user = await self._client.users.by_user_id(self.user_email).get()
            else:
                # App-only auth - need to specify a user
                raise ValueError("user_email required for app-only auth")
            return user
        
        result = asyncio.run(get_me())
        self._me = {
            "Id": result.id,
            "DisplayName": result.display_name,
            "Email": result.mail or result.user_principal_name,
            "JobTitle": result.job_title,
            "Department": result.department,
            "OfficeLocation": result.office_location,
        }
    
    def reload(self) -> None:
        """Refresh data (Graph API is live, so this is a no-op)."""
        pass
    
    # =========================================================================
    # User / Identity
    # =========================================================================
    
    def get_me(self) -> dict:
        """Get the current user's profile."""
        return self._me
    
    def get_my_email(self) -> str:
        """Get the current user's email address."""
        return self._me.get("Email", "")
    
    # =========================================================================
    # Colleagues / Directory
    # =========================================================================
    
    def get_colleagues(self, department: str | None = None, limit: int = 20) -> list[dict]:
        """Get colleagues from Azure AD."""
        import asyncio
        
        async def fetch_users():
            # Build filter
            filter_str = None
            if department:
                filter_str = f"department eq '{department}'"
            
            users = await self._client.users.get(
                request_configuration=lambda config: (
                    setattr(config.query_parameters, "top", limit),
                    setattr(config.query_parameters, "filter", filter_str) if filter_str else None,
                    setattr(config.query_parameters, "select", ["id", "displayName", "mail", "jobTitle", "department"])
                )
            )
            return users.value
        
        results = asyncio.run(fetch_users())
        my_email = self.get_my_email().lower()
        
        return [
            {
                "Id": u.id,
                "DisplayName": u.display_name,
                "Email": u.mail or u.user_principal_name,
                "JobTitle": u.job_title,
                "Department": u.department,
            }
            for u in results
            if (u.mail or "").lower() != my_email
        ]
    
    def search_colleagues(self, query: str, limit: int = 10) -> list[dict]:
        """Search colleagues by name or email."""
        import asyncio
        
        async def search():
            # Use $search or $filter
            filter_str = f"startswith(displayName, '{query}') or startswith(mail, '{query}')"
            
            users = await self._client.users.get(
                request_configuration=lambda config: (
                    setattr(config.query_parameters, "top", limit),
                    setattr(config.query_parameters, "filter", filter_str),
                    setattr(config.query_parameters, "select", ["id", "displayName", "mail", "jobTitle", "department"])
                )
            )
            return users.value
        
        results = asyncio.run(search())
        my_email = self.get_my_email().lower()
        
        return [
            {
                "Id": u.id,
                "DisplayName": u.display_name,
                "Email": u.mail or u.user_principal_name,
                "JobTitle": u.job_title,
                "Department": u.department,
            }
            for u in results
            if (u.mail or "").lower() != my_email
        ]
    
    def get_org_structure(self) -> dict:
        """Get organization structure (simplified for Graph)."""
        colleagues = self.get_colleagues(limit=100)
        
        departments: dict[str, list] = {}
        my_email = self.get_my_email().lower()
        
        for user in colleagues:
            dept = user.get("Department") or "Unknown"
            if dept not in departments:
                departments[dept] = []
            departments[dept].append({
                "name": user.get("DisplayName"),
                "title": user.get("JobTitle"),
                "email": user.get("Email"),
                "is_me": (user.get("Email") or "").lower() == my_email
            })
        
        return {
            "my_department": self._me.get("Department", "Unknown"),
            "departments": [
                {"name": dept, "count": len(users), "members": users}
                for dept, users in sorted(departments.items())
            ]
        }
    
    # =========================================================================
    # Emails
    # =========================================================================
    
    def get_all_emails(self) -> list[dict]:
        """Get all emails (limited for performance)."""
        # For indexing, get recent emails
        return self.get_inbox(limit=100) + self.get_sent_items(limit=100)
    
    def get_email_by_id(self, email_id: str) -> dict | None:
        """Get a specific email by ID."""
        import asyncio
        
        async def fetch():
            msg = await self._client.users.by_user_id(self.user_email).messages.by_message_id(email_id).get()
            return msg
        
        try:
            msg = asyncio.run(fetch())
            return self._convert_message(msg)
        except Exception:
            return None
    
    def _convert_message(self, msg) -> dict:
        """Convert Graph message to our format."""
        return {
            "Id": msg.id,
            "Subject": msg.subject,
            "From": msg.from_.email_address.address if msg.from_ else "",
            "FromName": msg.from_.email_address.name if msg.from_ else "",
            "To": [r.email_address.address for r in (msg.to_recipients or [])],
            "Body": msg.body.content if msg.body else "",
            "ReceivedDate": msg.received_date_time.isoformat() if msg.received_date_time else "",
            "IsRead": msg.is_read,
            "Importance": msg.importance.value if msg.importance else "Normal",
            "HasAttachments": msg.has_attachments,
            "FolderPath": "Inbox"  # Simplified
        }
    
    def get_inbox(self, limit: int = 20, unread_only: bool = False) -> list[dict]:
        """Get inbox emails."""
        import asyncio
        
        async def fetch():
            filter_str = "isRead eq false" if unread_only else None
            
            messages = await self._client.users.by_user_id(self.user_email).mail_folders.by_mail_folder_id("inbox").messages.get(
                request_configuration=lambda config: (
                    setattr(config.query_parameters, "top", limit),
                    setattr(config.query_parameters, "filter", filter_str) if filter_str else None,
                    setattr(config.query_parameters, "orderby", ["receivedDateTime desc"])
                )
            )
            return messages.value
        
        results = asyncio.run(fetch())
        return [self._convert_message(m) for m in results]
    
    def get_sent_items(self, limit: int = 20) -> list[dict]:
        """Get sent emails."""
        import asyncio
        
        async def fetch():
            messages = await self._client.users.by_user_id(self.user_email).mail_folders.by_mail_folder_id("sentitems").messages.get(
                request_configuration=lambda config: (
                    setattr(config.query_parameters, "top", limit),
                    setattr(config.query_parameters, "orderby", ["sentDateTime desc"])
                )
            )
            return messages.value
        
        results = asyncio.run(fetch())
        emails = [self._convert_message(m) for m in results]
        for e in emails:
            e["FolderPath"] = "Sent Items"
        return emails
    
    def get_unread_count(self) -> int:
        """Get count of unread emails."""
        import asyncio
        
        async def fetch():
            folder = await self._client.users.by_user_id(self.user_email).mail_folders.by_mail_folder_id("inbox").get()
            return folder.unread_item_count
        
        return asyncio.run(fetch())
    
    # =========================================================================
    # Calendar / Meetings
    # =========================================================================
    
    def get_all_meetings(self) -> list[dict]:
        """Get all meetings (for indexing)."""
        return self.get_calendar(days=30, include_past=True)
    
    def get_meeting_by_id(self, meeting_id: str) -> dict | None:
        """Get a specific meeting by ID."""
        import asyncio
        
        async def fetch():
            event = await self._client.users.by_user_id(self.user_email).events.by_event_id(meeting_id).get()
            return event
        
        try:
            event = asyncio.run(fetch())
            return self._convert_event(event)
        except Exception:
            return None
    
    def _convert_event(self, event) -> dict:
        """Convert Graph event to our format."""
        return {
            "Id": event.id,
            "Subject": event.subject,
            "StartTime": event.start.date_time if event.start else "",
            "EndTime": event.end.date_time if event.end else "",
            "Location": event.location.display_name if event.location else "",
            "Organizer": event.organizer.email_address.address if event.organizer else "",
            "Attendees": [a.email_address.address for a in (event.attendees or [])],
            "Body": event.body.content if event.body else "",
            "IsAllDay": event.is_all_day,
            "IsCancelled": event.is_cancelled,
        }
    
    def get_calendar(self, days: int = 7, include_past: bool = False) -> list[dict]:
        """Get calendar events."""
        import asyncio
        
        now = datetime.now()
        start = now - timedelta(days=7) if include_past else now
        end = now + timedelta(days=days)
        
        async def fetch():
            events = await self._client.users.by_user_id(self.user_email).calendar_view.get(
                request_configuration=lambda config: (
                    setattr(config.query_parameters, "start_date_time", start.isoformat()),
                    setattr(config.query_parameters, "end_date_time", end.isoformat()),
                    setattr(config.query_parameters, "top", 50),
                    setattr(config.query_parameters, "orderby", ["start/dateTime"])
                )
            )
            return events.value
        
        results = asyncio.run(fetch())
        return [self._convert_event(e) for e in results]
    
    def get_todays_meetings(self) -> list[dict]:
        """Get today's meetings."""
        import asyncio
        
        today = datetime.now().date()
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        
        async def fetch():
            events = await self._client.users.by_user_id(self.user_email).calendar_view.get(
                request_configuration=lambda config: (
                    setattr(config.query_parameters, "start_date_time", start.isoformat()),
                    setattr(config.query_parameters, "end_date_time", end.isoformat()),
                    setattr(config.query_parameters, "orderby", ["start/dateTime"])
                )
            )
            return events.value
        
        results = asyncio.run(fetch())
        return [self._convert_event(e) for e in results]
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    def get_email_stats(self) -> dict:
        """Get email statistics."""
        inbox = self.get_inbox(limit=50)
        sent = self.get_sent_items(limit=50)
        unread_count = self.get_unread_count()
        
        # Top senders
        sender_counts: dict[str, int] = {}
        for email in inbox:
            sender = email.get("FromName") or email.get("From", "Unknown")
            sender_counts[sender] = sender_counts.get(sender, 0) + 1
        
        top_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        high_importance = len([e for e in inbox if e.get("Importance") == "High"])
        
        return {
            "inbox_count": len(inbox),
            "sent_count": len(sent),
            "unread_count": unread_count,
            "high_importance": high_importance,
            "top_senders": [{"name": s[0], "count": s[1]} for s in top_senders]
        }
    
    def get_meeting_stats(self) -> dict:
        """Get meeting statistics."""
        all_meetings = self.get_calendar(days=30, include_past=True)
        now = datetime.now()
        my_email = self.get_my_email().lower()
        
        upcoming = []
        past = []
        organized_by_me = []
        
        for meeting in all_meetings:
            start_str = meeting.get("StartTime", "")
            if start_str:
                try:
                    start_time = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    if start_time > now:
                        upcoming.append(meeting)
                    else:
                        past.append(meeting)
                except ValueError:
                    pass
            
            if meeting.get("Organizer", "").lower() == my_email:
                organized_by_me.append(meeting)
        
        return {
            "total_meetings": len(all_meetings),
            "upcoming": len(upcoming),
            "past": len(past),
            "organized_by_me": len(organized_by_me),
            "today": len(self.get_todays_meetings())
        }
