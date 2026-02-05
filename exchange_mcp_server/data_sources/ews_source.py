"""
Exchange Web Services (EWS) Data Source

Connects to on-premises Exchange Server or Exchange Online via EWS.
Useful for environments that don't use Microsoft 365 or need EWS compatibility.

Install dependencies:
    pip install exchangelib

Usage:
    source = EWSDataSource(
        server="mail.company.com",  # Or "outlook.office365.com" for O365
        email="user@company.com",
        username="DOMAIN\\username",  # Or just email for O365
        password="your-password"
    )
    source.initialize()
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from exchange_mcp_server.data_sources import DataSourceBase

logger = logging.getLogger("exchange-mcp.ews")


class EWSDataSource(DataSourceBase):
    """
    Data source using Exchange Web Services (EWS).
    
    Works with on-premises Exchange Server (2010+) and Exchange Online.
    Uses the exchangelib Python library.
    """
    
    def __init__(
        self,
        email: str,
        username: str,
        password: str,
        server: str | None = None,
        autodiscover: bool = True,
    ):
        """
        Initialize EWS data source.
        
        Args:
            email: User's email address
            username: Login username (email or DOMAIN\\user)
            password: User's password
            server: EWS server URL (optional if autodiscover=True)
            autodiscover: Use Exchange autodiscover to find server
        """
        self.email = email
        self.username = username
        self.password = password
        self.server = server
        self.autodiscover = autodiscover
        
        self._account = None
        self._me: dict = {}
    
    def initialize(self) -> None:
        """Initialize the EWS connection."""
        try:
            from exchangelib import Credentials, Account, Configuration, DELEGATE
            from exchangelib.protocol import BaseProtocol, NoVerifyHTTPAdapter
        except ImportError as e:
            raise ImportError(
                "exchangelib not installed. Run:\n"
                "  pip install exchangelib"
            ) from e
        
        logger.info(f"Connecting to Exchange as {self.email}...")
        
        # Create credentials
        credentials = Credentials(self.username, self.password)
        
        if self.autodiscover:
            # Use autodiscover
            self._account = Account(
                self.email,
                credentials=credentials,
                autodiscover=True,
                access_type=DELEGATE
            )
        else:
            # Manual configuration
            config = Configuration(
                server=self.server,
                credentials=credentials
            )
            self._account = Account(
                self.email,
                config=config,
                autodiscover=False,
                access_type=DELEGATE
            )
        
        # Build user profile
        self._me = {
            "Id": self.email,
            "DisplayName": self._account.root.account.primary_smtp_address.split("@")[0],  # Simplified
            "Email": self.email,
            "JobTitle": "",
            "Department": "",
        }
        
        logger.info(f"Connected to Exchange: {self._account.protocol.server}")
    
    def reload(self) -> None:
        """Refresh data (EWS is live, so this is a no-op)."""
        pass
    
    # =========================================================================
    # User / Identity
    # =========================================================================
    
    def get_me(self) -> dict:
        """Get the current user's profile."""
        return self._me
    
    def get_my_email(self) -> str:
        """Get the current user's email address."""
        return self.email
    
    # =========================================================================
    # Colleagues / Directory
    # =========================================================================
    
    def get_colleagues(self, department: str | None = None, limit: int = 20) -> list[dict]:
        """
        Get colleagues using Exchange GAL (Global Address List).
        Note: EWS has limited directory capabilities compared to Graph.
        """
        # EWS doesn't have great directory search - would need LDAP for full AD
        logger.warning("EWS has limited directory capabilities. Consider using LDAP for full AD access.")
        return []
    
    def search_colleagues(self, query: str, limit: int = 10) -> list[dict]:
        """Search colleagues using Exchange resolve names."""
        from exchangelib import ResolveNames
        
        results = []
        try:
            # Use ResolveName to search GAL
            for resolution in self._account.protocol.resolve_names(query):
                if hasattr(resolution, 'mailbox'):
                    results.append({
                        "Id": resolution.mailbox.email_address,
                        "DisplayName": resolution.mailbox.name,
                        "Email": resolution.mailbox.email_address,
                        "JobTitle": "",
                        "Department": "",
                    })
                    if len(results) >= limit:
                        break
        except Exception as e:
            logger.warning(f"Error searching GAL: {e}")
        
        return results
    
    def get_org_structure(self) -> dict:
        """Get organization structure (not available via EWS)."""
        logger.warning("Organization structure not available via EWS. Use LDAP/AD.")
        return {
            "my_department": self._me.get("Department", "Unknown"),
            "departments": []
        }
    
    # =========================================================================
    # Emails
    # =========================================================================
    
    def _convert_message(self, msg) -> dict:
        """Convert EWS message to our format."""
        return {
            "Id": msg.id if hasattr(msg, 'id') else str(msg.item_id),
            "Subject": msg.subject or "",
            "From": msg.sender.email_address if msg.sender else "",
            "FromName": msg.sender.name if msg.sender else "",
            "To": [r.email_address for r in (msg.to_recipients or [])],
            "Body": msg.text_body or (msg.body or ""),
            "ReceivedDate": msg.datetime_received.isoformat() if msg.datetime_received else "",
            "IsRead": msg.is_read,
            "Importance": str(msg.importance) if msg.importance else "Normal",
            "HasAttachments": bool(msg.attachments),
            "FolderPath": "Inbox"
        }
    
    def get_all_emails(self) -> list[dict]:
        """Get all emails (limited for performance)."""
        return self.get_inbox(limit=100) + self.get_sent_items(limit=100)
    
    def get_email_by_id(self, email_id: str) -> dict | None:
        """Get a specific email by ID."""
        try:
            from exchangelib import Message
            msg = self._account.inbox.get(id=email_id)
            return self._convert_message(msg)
        except Exception:
            return None
    
    def get_inbox(self, limit: int = 20, unread_only: bool = False) -> list[dict]:
        """Get inbox emails."""
        from exchangelib import Message
        
        queryset = self._account.inbox.filter(is_read=False) if unread_only else self._account.inbox.all()
        queryset = queryset.order_by('-datetime_received')[:limit]
        
        return [self._convert_message(m) for m in queryset]
    
    def get_sent_items(self, limit: int = 20) -> list[dict]:
        """Get sent emails."""
        queryset = self._account.sent.all().order_by('-datetime_sent')[:limit]
        
        emails = [self._convert_message(m) for m in queryset]
        for e in emails:
            e["FolderPath"] = "Sent Items"
        return emails
    
    def get_unread_count(self) -> int:
        """Get count of unread emails."""
        return self._account.inbox.unread_count
    
    # =========================================================================
    # Calendar / Meetings
    # =========================================================================
    
    def _convert_event(self, event) -> dict:
        """Convert EWS calendar item to our format."""
        return {
            "Id": event.id if hasattr(event, 'id') else str(event.item_id),
            "Subject": event.subject or "",
            "StartTime": event.start.isoformat() if event.start else "",
            "EndTime": event.end.isoformat() if event.end else "",
            "Location": event.location or "",
            "Organizer": event.organizer.email_address if event.organizer else "",
            "Attendees": [a.mailbox.email_address for a in (event.required_attendees or [])],
            "Body": event.text_body or (event.body or ""),
            "IsAllDay": event.is_all_day,
            "IsCancelled": event.is_cancelled,
        }
    
    def get_all_meetings(self) -> list[dict]:
        """Get all meetings (for indexing)."""
        return self.get_calendar(days=30, include_past=True)
    
    def get_meeting_by_id(self, meeting_id: str) -> dict | None:
        """Get a specific meeting by ID."""
        try:
            event = self._account.calendar.get(id=meeting_id)
            return self._convert_event(event)
        except Exception:
            return None
    
    def get_calendar(self, days: int = 7, include_past: bool = False) -> list[dict]:
        """Get calendar events."""
        from exchangelib import EWSDateTime, EWSTimeZone
        
        tz = EWSTimeZone.localzone()
        now = datetime.now()
        start = now - timedelta(days=7) if include_past else now
        end = now + timedelta(days=days)
        
        start_ews = tz.localize(EWSDateTime(start.year, start.month, start.day))
        end_ews = tz.localize(EWSDateTime(end.year, end.month, end.day, 23, 59, 59))
        
        queryset = self._account.calendar.view(start=start_ews, end=end_ews)
        
        return [self._convert_event(e) for e in queryset]
    
    def get_todays_meetings(self) -> list[dict]:
        """Get today's meetings."""
        from exchangelib import EWSDateTime, EWSTimeZone
        
        tz = EWSTimeZone.localzone()
        today = datetime.now().date()
        
        start = tz.localize(EWSDateTime(today.year, today.month, today.day))
        end = tz.localize(EWSDateTime(today.year, today.month, today.day, 23, 59, 59))
        
        queryset = self._account.calendar.view(start=start, end=end)
        
        return [self._convert_event(e) for e in queryset]
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    def get_email_stats(self) -> dict:
        """Get email statistics."""
        inbox = self.get_inbox(limit=50)
        sent = self.get_sent_items(limit=50)
        unread_count = self.get_unread_count()
        
        sender_counts: dict[str, int] = {}
        for email in inbox:
            sender = email.get("FromName") or email.get("From", "Unknown")
            sender_counts[sender] = sender_counts.get(sender, 0) + 1
        
        top_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        high_importance = len([e for e in inbox if "high" in e.get("Importance", "").lower()])
        
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
                    start_time = datetime.fromisoformat(start_str)
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
