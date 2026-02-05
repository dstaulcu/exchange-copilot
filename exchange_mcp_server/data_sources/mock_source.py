"""
Mock Data Source - Reads from local JSON file.

This is the current implementation, refactored to implement the DataSourceBase interface.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any

from exchange_mcp_server.data_sources import DataSourceBase


class MockDataSource(DataSourceBase):
    """Data source that reads from a local JSON cache file."""
    
    def __init__(self, cache_path: str | Path | None = None):
        """
        Initialize mock data source.
        
        Args:
            cache_path: Path to JSON data file. Should be set via DATA_FILE env var.
        """
        import os
        if cache_path is None:
            # Get from environment or use default path
            default_data_path = str(Path(__file__).parent.parent.parent / "data")
            data_path = os.getenv("DATA_PATH", default_data_path)
            cache_path = os.getenv("DATA_FILE", os.path.join(data_path, "exchange_mcp.json"))
        
        self.cache_path = Path(cache_path)
        self.data: dict[str, Any] = {}
        self.protagonist: dict[str, Any] = {}
    
    def initialize(self) -> None:
        """Load data from JSON file."""
        self._load_data()
    
    def _load_data(self):
        """Load data from JSON cache file."""
        if self.cache_path.exists():
            with open(self.cache_path, "r", encoding="utf-8-sig") as f:
                self.data = json.load(f)
            self.protagonist = self.data.get("Protagonist", {})
        else:
            raise FileNotFoundError(f"Cache file not found: {self.cache_path}")
    
    def reload(self) -> None:
        """Reload data from cache file."""
        self._load_data()
    
    # =========================================================================
    # User / Identity
    # =========================================================================
    
    def get_me(self) -> dict:
        """Get the protagonist user's info."""
        user_id = self.protagonist.get("Id")
        if user_id:
            return self.data.get("Users", {}).get(user_id, self.protagonist)
        return self.protagonist
    
    def get_my_email(self) -> str:
        """Get the protagonist's email address."""
        return self.protagonist.get("Email", "")
    
    # =========================================================================
    # Colleagues / Directory
    # =========================================================================
    
    def get_colleagues(self, department: str | None = None, limit: int = 20) -> list[dict]:
        """Get colleagues, optionally filtered by department."""
        my_email = self.get_my_email().lower()
        colleagues = [
            u for u in self.data.get("Users", {}).values()
            if u.get("Email", "").lower() != my_email
        ]
        
        if department:
            colleagues = [u for u in colleagues if u.get("Department", "").lower() == department.lower()]
        
        colleagues.sort(key=lambda u: u.get("DisplayName", ""))
        return colleagues[:limit]
    
    def search_colleagues(self, query: str, limit: int = 10) -> list[dict]:
        """Search colleagues by name or email."""
        query_lower = query.lower()
        my_email = self.get_my_email().lower()
        results = []
        
        for user in self.data.get("Users", {}).values():
            if user.get("Email", "").lower() == my_email:
                continue
            name = user.get("DisplayName", "").lower()
            email = user.get("Email", "").lower()
            dept = user.get("Department", "").lower()
            
            if query_lower in name or query_lower in email or query_lower in dept:
                results.append(user)
        
        results.sort(key=lambda u: u.get("DisplayName", ""))
        return results[:limit]
    
    def get_org_structure(self) -> dict:
        """Get organization structure grouped by department."""
        departments: dict[str, list] = {}
        my_email = self.get_my_email().lower()
        
        for user in self.data.get("Users", {}).values():
            dept = user.get("Department", "Unknown")
            if dept not in departments:
                departments[dept] = []
            
            user_info = {
                "name": user.get("DisplayName"),
                "title": user.get("JobTitle"),
                "email": user.get("Email"),
                "is_me": user.get("Email", "").lower() == my_email
            }
            departments[dept].append(user_info)
        
        for dept in departments:
            departments[dept].sort(key=lambda u: (not u.get("is_me", False), u.get("name", "")))
        
        return {
            "my_department": self.protagonist.get("Department", "Unknown"),
            "departments": [
                {"name": dept, "count": len(users), "members": users}
                for dept, users in sorted(departments.items())
            ]
        }
    
    # =========================================================================
    # Emails
    # =========================================================================
    
    def get_all_emails(self) -> list[dict]:
        """Get all emails for indexing."""
        return list(self.data.get("Emails", {}).values())
    
    def get_email_by_id(self, email_id: str) -> dict | None:
        """Get an email by ID."""
        return self.data.get("Emails", {}).get(email_id)
    
    def get_inbox(self, limit: int = 20, unread_only: bool = False) -> list[dict]:
        """Get emails from inbox (emails TO me)."""
        emails = [
            e for e in self.data.get("Emails", {}).values()
            if e.get("FolderPath") == "Inbox"
        ]
        
        if unread_only:
            emails = [e for e in emails if not e.get("IsRead", False)]
        
        emails.sort(key=lambda e: e.get("ReceivedDate", ""), reverse=True)
        return emails[:limit]
    
    def get_sent_items(self, limit: int = 20) -> list[dict]:
        """Get sent emails (emails FROM me)."""
        emails = [
            e for e in self.data.get("Emails", {}).values()
            if e.get("FolderPath") == "Sent Items"
        ]
        
        emails.sort(key=lambda e: e.get("ReceivedDate", ""), reverse=True)
        return emails[:limit]
    
    def get_unread_count(self) -> int:
        """Get count of unread emails in inbox."""
        return len([
            e for e in self.data.get("Emails", {}).values()
            if e.get("FolderPath") == "Inbox" and not e.get("IsRead", False)
        ])
    
    # =========================================================================
    # Calendar / Meetings
    # =========================================================================
    
    def get_all_meetings(self) -> list[dict]:
        """Get all meetings for indexing."""
        return list(self.data.get("Meetings", {}).values())
    
    def get_meeting_by_id(self, meeting_id: str) -> dict | None:
        """Get a meeting by ID."""
        return self.data.get("Meetings", {}).get(meeting_id)
    
    def _parse_datetime(self, dt_str: str) -> datetime | None:
        """Parse datetime from various formats."""
        if not dt_str:
            return None
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d %H:%M:%S"]:
            try:
                return datetime.strptime(dt_str, fmt)
            except ValueError:
                continue
        return None
    
    def get_calendar(self, days: int = 7, include_past: bool = False) -> list[dict]:
        """Get upcoming meetings from my calendar."""
        meetings = list(self.data.get("Meetings", {}).values())
        
        now = datetime.now()
        start_date = now - timedelta(days=7) if include_past else now
        end_date = now + timedelta(days=days)
        
        result = []
        for meeting in meetings:
            start_time = self._parse_datetime(meeting.get("StartTime", ""))
            if start_time and start_date <= start_time <= end_date:
                result.append(meeting)
        
        result.sort(key=lambda m: m.get("StartTime", ""))
        return result
    
    def get_todays_meetings(self) -> list[dict]:
        """Get today's meetings."""
        today = datetime.now().date()
        meetings = []
        
        for meeting in self.data.get("Meetings", {}).values():
            start_time = self._parse_datetime(meeting.get("StartTime", ""))
            if start_time and start_time.date() == today:
                meetings.append(meeting)
        
        meetings.sort(key=lambda m: m.get("StartTime", ""))
        return meetings
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    def get_email_stats(self) -> dict:
        """Get email statistics."""
        all_emails = list(self.data.get("Emails", {}).values())
        inbox = [e for e in all_emails if e.get("FolderPath") == "Inbox"]
        sent = [e for e in all_emails if e.get("FolderPath") == "Sent Items"]
        unread = [e for e in inbox if not e.get("IsRead", False)]
        high_importance = [e for e in inbox if e.get("Importance") == "High"]
        
        # Top senders
        sender_counts: dict[str, int] = {}
        for email in inbox:
            sender = email.get("FromName") or email.get("From", "Unknown")
            sender_counts[sender] = sender_counts.get(sender, 0) + 1
        
        top_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "inbox_count": len(inbox),
            "sent_count": len(sent),
            "unread_count": len(unread),
            "high_importance": len(high_importance),
            "top_senders": [{"name": s[0], "count": s[1]} for s in top_senders]
        }
    
    def get_meeting_stats(self) -> dict:
        """Get meeting statistics."""
        all_meetings = list(self.data.get("Meetings", {}).values())
        now = datetime.now()
        my_email = self.get_my_email().lower()
        
        upcoming = []
        past = []
        organized_by_me = []
        
        for meeting in all_meetings:
            start_time = self._parse_datetime(meeting.get("StartTime", ""))
            if start_time:
                if start_time > now:
                    upcoming.append(meeting)
                else:
                    past.append(meeting)
                
                if meeting.get("Organizer", "").lower() == my_email:
                    organized_by_me.append(meeting)
        
        return {
            "total_meetings": len(all_meetings),
            "upcoming": len(upcoming),
            "past": len(past),
            "organized_by_me": len(organized_by_me),
            "today": len(self.get_todays_meetings())
        }
