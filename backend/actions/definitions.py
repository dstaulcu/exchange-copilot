"""
Action Definitions - Example actions demonstrating the framework.

These actions show how to compose tool calls into reusable workflows.
Each action is self-documenting and testable.
"""

from typing import Any, Dict, List
from backend.actions.base import Action, ActionContext, ActionResult, ActionStatus, registry


@registry.register
class DailySummaryAction(Action):
    """
    Generate a daily summary of emails and meetings.
    
    Workflow:
    1. Get user info
    2. Get today's meetings
    3. Get unread inbox emails
    4. Compile summary
    """
    name = "daily_summary"
    description = "Generate a daily summary of emails and meetings"
    tags = ["email", "calendar", "summary"]
    
    def execute(self, context: ActionContext) -> ActionResult:
        # Step 1: Get user info
        me = self.call_tool("whoami")
        context.set("user", me)
        
        # Step 2: Get today's meetings
        meetings = self.call_tool("get_todays_meetings")
        context.set("meetings", meetings)
        
        # Step 3: Get unread emails
        inbox = self.call_tool("get_inbox", limit=20, unread_only=True)
        context.set("inbox", inbox)
        
        # Step 4: Compile summary
        summary = {
            "user": me.get("name"),
            "date": meetings.get("date", "today"),
            "meetings_today": meetings.get("count", 0),
            "unread_emails": inbox.get("unread_total", 0),
            "high_priority_emails": [
                e for e in inbox.get("emails", [])
                if e.get("importance") == "High"
            ],
            "next_meeting": meetings.get("meetings", [{}])[0] if meetings.get("meetings") else None,
        }
        
        return self.complete(output=summary)


@registry.register
class EmailThreadAction(Action):
    """
    Retrieve an email thread for a given email ID.
    
    Workflow:
    1. Read the initial email
    2. Search for related emails by subject/sender
    3. Return chronological thread
    """
    name = "get_email_thread"
    description = "Get full email thread for a given email"
    tags = ["email", "search"]
    
    def execute(self, context: ActionContext) -> ActionResult:
        email_id = context.get("email_id")
        if not email_id:
            return self.fail("email_id required in context")
        
        # Step 1: Get the original email
        email = self.call_tool("read_email", email_id=email_id)
        if email.get("error"):
            return self.fail(f"Email not found: {email_id}")
        
        context.set("original_email", email)
        
        # Step 2: Search for related emails
        subject = email.get("subject", "")
        # Remove Re:/Fwd: prefixes for search
        clean_subject = subject
        for prefix in ["Re: ", "RE: ", "Fwd: ", "FWD: ", "Fw: "]:
            clean_subject = clean_subject.replace(prefix, "")
        
        related = self.call_tool("search_emails", query=clean_subject, limit=10)
        
        # Step 3: Build thread
        thread = {
            "original": email,
            "subject": subject,
            "thread_count": related.get("count", 1),
            "messages": related.get("results", []),
        }
        
        return self.complete(output=thread)


@registry.register
class MeetingPrepAction(Action):
    """
    Prepare for an upcoming meeting.
    
    Workflow:
    1. Get meeting details
    2. Find relevant emails about the topic
    3. Look up attendee info
    4. Compile prep document
    """
    name = "meeting_prep"
    description = "Prepare background info for a meeting"
    tags = ["calendar", "email", "lookup"]
    
    def execute(self, context: ActionContext) -> ActionResult:
        meeting_id = context.get("meeting_id")
        if not meeting_id:
            # If no specific meeting, get next meeting
            today = self.call_tool("get_todays_meetings")
            if today.get("meetings"):
                meeting = today["meetings"][0]
            else:
                calendar = self.call_tool("get_calendar", days=7)
                if calendar.get("meetings"):
                    meeting = calendar["meetings"][0]
                else:
                    return self.fail("No upcoming meetings found")
        else:
            meetings = self.call_tool("search_meetings", query=meeting_id, limit=1)
            if not meetings.get("results"):
                return self.fail(f"Meeting not found: {meeting_id}")
            meeting = meetings["results"][0]
        
        context.set("meeting", meeting)
        
        # Search for relevant emails
        subject = meeting.get("subject", "")
        related_emails = self.call_tool("search_emails", query=subject, limit=5)
        
        # Look up organizer
        organizer_name = meeting.get("organizer", "")
        if organizer_name:
            organizer = self.call_tool("find_colleague", name=organizer_name)
        else:
            organizer = None
        
        prep = {
            "meeting": meeting,
            "related_emails": related_emails.get("results", []),
            "organizer_info": organizer,
            "prep_notes": f"Meeting: {subject}",
        }
        
        return self.complete(output=prep)


@registry.register
class ColleagueLookupAction(Action):
    """
    Comprehensive colleague lookup with recent interactions.
    
    Workflow:
    1. Find colleague by name
    2. Search for emails from/to them
    3. Search for meetings with them
    """
    name = "colleague_lookup"
    description = "Look up a colleague with recent interactions"
    tags = ["lookup", "email", "calendar"]
    
    def execute(self, context: ActionContext) -> ActionResult:
        name = context.get("colleague_name")
        if not name:
            return self.fail("colleague_name required in context")
        
        # Step 1: Find the colleague
        colleague = self.call_tool("find_colleague", name=name)
        if colleague.get("error") or not colleague.get("name"):
            return self.fail(f"Colleague not found: {name}")
        
        context.set("colleague", colleague)
        
        # Step 2: Find recent emails
        email_query = f"from:{name} OR to:{name}"
        emails = self.call_tool("search_emails", query=name, limit=10)
        
        # Step 3: Find meetings together
        meetings = self.call_tool("search_meetings", query=name, limit=5)
        
        result = {
            "colleague": colleague,
            "recent_emails": emails.get("results", []),
            "shared_meetings": meetings.get("results", []),
        }
        
        return self.complete(output=result)


@registry.register  
class InboxTriageAction(Action):
    """
    Triage inbox by priority and category.
    
    Workflow:
    1. Get all unread emails
    2. Categorize by sender type (manager, direct reports, external)
    3. Sort by priority
    """
    name = "inbox_triage"
    description = "Triage unread inbox by priority"
    tags = ["email", "summary"]
    
    def execute(self, context: ActionContext) -> ActionResult:
        # Get user info for context
        me = self.call_tool("whoami")
        my_dept = me.get("department", "")
        
        # Get unread inbox
        inbox = self.call_tool("get_inbox", limit=50, unread_only=True)
        emails = inbox.get("emails", [])
        
        # Categorize
        high_priority = []
        same_dept = []
        external = []
        other = []
        
        for email in emails:
            if email.get("importance") == "High":
                high_priority.append(email)
            # Additional categorization would require more data
            else:
                other.append(email)
        
        triage = {
            "total_unread": inbox.get("unread_total", 0),
            "high_priority": high_priority,
            "high_priority_count": len(high_priority),
            "other": other,
            "recommendation": (
                f"You have {len(high_priority)} high-priority emails to address first."
                if high_priority else "No urgent emails at this time."
            ),
        }
        
        return self.complete(output=triage)


@registry.register
class DailyBriefingAction(Action):
    """
    Generate a printable daily briefing with meeting intelligence.
    
    This action prepares you for today's meetings by:
    1. Getting today's calendar with meeting details
    2. For each meeting, identifying key topics from subject/body
    3. Searching recent emails for relevant conversations
    4. Identifying key collaborators and recent findings
    5. Compiling a formatted briefing document
    
    Output is structured for printing/carrying to meetings.
    """
    name = "daily_briefing"
    description = "Generate printable meeting intelligence briefing for today"
    tags = ["calendar", "email", "search", "prep", "briefing"]
    
    def execute(self, context: ActionContext) -> ActionResult:
        # Step 1: Get user info and today's meetings
        me = self.call_tool("whoami")
        context.set("user", me)
        
        today_meetings = self.call_tool("get_todays_meetings")
        meetings = today_meetings.get("meetings", [])
        
        if not meetings:
            return self.complete(output={
                "date": today_meetings.get("date", "today"),
                "user": me.get("name"),
                "message": "No meetings scheduled for today.",
                "briefings": []
            })
        
        context.set("meetings_count", len(meetings))
        
        # Step 2: Get recent emails from inbox and sent
        inbox = self.call_tool("get_inbox", limit=50, unread_only=False)
        sent = self.call_tool("get_sent", limit=30)
        
        all_recent_emails = inbox.get("emails", []) + sent.get("emails", [])
        context.set("email_pool_size", len(all_recent_emails))
        
        # Step 3: Process each meeting
        briefings = []
        for meeting in meetings:
            briefing = self._process_meeting(meeting, all_recent_emails, context)
            briefings.append(briefing)
        
        # Step 4: Detect scheduling conflicts and suggest alternatives
        conflicts = self._detect_conflicts(meetings, all_recent_emails)
        
        # Step 5: Compile final briefing document
        output = {
            "date": today_meetings.get("date", "today"),
            "user": me.get("name"),
            "generated_at": context.get("timestamp", "now"),
            "meetings_count": len(meetings),
            "conflicts": conflicts,
            "briefings": briefings,
            "print_ready": self._format_for_print(briefings, me, today_meetings.get("date"), conflicts),
        }
        
        return self.complete(output=output)
    
    def _detect_conflicts(self, meetings: List[Dict[str, Any]], emails: List[Dict] = None) -> List[Dict[str, Any]]:
        """Detect overlapping meetings and suggest alternative contributors."""
        conflicts = []
        
        # Parse meeting times and check for overlaps
        for i, m1 in enumerate(meetings):
            for m2 in meetings[i+1:]:
                start1 = m1.get("start", "")
                end1 = m1.get("end", "")
                start2 = m2.get("start", "")
                end2 = m2.get("end", "")
                
                is_conflict = False
                # Simple string comparison works for ISO format times
                # Overlap if: start1 < end2 AND start2 < end1
                if start1 and start2 and end1 and end2:
                    if start1 < end2 and start2 < end1:
                        is_conflict = True
                elif start1 and start2:
                    # Fallback: check if start times are the same
                    if start1 == start2:
                        is_conflict = True
                
                if is_conflict:
                    conflict = {
                        "meeting1": m1.get("subject", "Unknown"),
                        "meeting2": m2.get("subject", "Unknown"),
                        "time1": start1,
                        "time2": start2,
                        "alternatives1": [],
                        "alternatives2": [],
                    }
                    
                    # Find alternative contributors for each conflicting meeting
                    if emails:
                        conflict["alternatives1"] = self._find_alternative_contributors(
                            m1, emails, exclude=m1.get("attendees", [])
                        )
                        conflict["alternatives2"] = self._find_alternative_contributors(
                            m2, emails, exclude=m2.get("attendees", [])
                        )
                    
                    conflicts.append(conflict)
        
        return conflicts
    
    def _find_alternative_contributors(self, meeting: Dict[str, Any], emails: List[Dict], exclude: List = None) -> List[Dict]:
        """Find people discussing related topics who could potentially attend instead."""
        subject = meeting.get("subject", "")
        body = meeting.get("body", "")
        keywords = self._extract_keywords(subject, body)
        
        # Get names to exclude (current attendees)
        exclude_names = set()
        if exclude:
            for a in exclude:
                name = a.get("name", a) if isinstance(a, dict) else str(a)
                exclude_names.add(name.lower())
        
        # Find people in emails matching meeting keywords
        contributor_scores = {}
        
        for email in emails:
            email_subject = email.get("subject", "").lower()
            email_body = email.get("bodyPreview", email.get("body", "")).lower()
            email_text = f"{email_subject} {email_body}"
            
            # Check if email relates to meeting topics
            keyword_matches = sum(1 for kw in keywords if kw in email_text)
            if keyword_matches == 0:
                continue
            
            # Get sender
            sender = email.get("from", {})
            sender_name = sender.get("name", "") if isinstance(sender, dict) else str(sender)
            sender_email = sender.get("email", "") if isinstance(sender, dict) else ""
            
            if sender_name and sender_name.lower() not in exclude_names:
                key = sender_name
                if key not in contributor_scores:
                    contributor_scores[key] = {"name": sender_name, "email": sender_email, "score": 0, "topics": set()}
                contributor_scores[key]["score"] += keyword_matches
                contributor_scores[key]["topics"].update(kw for kw in keywords if kw in email_text)
        
        # Sort by score and return top alternatives
        alternatives = sorted(contributor_scores.values(), key=lambda x: x["score"], reverse=True)[:3]
        
        # Convert topics set to list for JSON serialization
        for alt in alternatives:
            alt["topics"] = list(alt["topics"])[:3]
        
        return alternatives
    
    def _process_meeting(self, meeting: Dict[str, Any], emails: List[Dict], context: ActionContext) -> Dict[str, Any]:
        """Process a single meeting and gather intelligence."""
        subject = meeting.get("subject", "")
        attendees = meeting.get("attendees", [])
        organizer = meeting.get("organizer", "")
        start_time = meeting.get("start", "")
        body = meeting.get("body", "")
        
        # Extract keywords from subject and body for searching
        keywords = self._extract_keywords(subject, body)
        
        # Find emails involving attendees
        attendee_emails = []
        attendee_names = [a.get("name", a) if isinstance(a, dict) else a for a in attendees]
        
        for email in emails:
            sender = email.get("from", {})
            sender_name = sender.get("name", "") if isinstance(sender, dict) else str(sender)
            recipients = email.get("to", [])
            
            # Check if any attendee is involved
            involved = False
            for attendee in attendee_names:
                if attendee and (
                    attendee.lower() in sender_name.lower() or
                    any(attendee.lower() in str(r).lower() for r in recipients)
                ):
                    involved = True
                    break
            
            if involved:
                attendee_emails.append(email)
        
        # Search for topic-related emails
        topic_emails = []
        if keywords:
            search_result = self.call_tool("search_emails", query=" ".join(keywords[:3]), limit=10)
            topic_emails = search_result.get("results", [])
        
        # Identify key collaborators (most frequent in related emails)
        collaborator_counts = {}
        for email in attendee_emails + topic_emails:
            sender = email.get("from", {})
            sender_name = sender.get("name", "") if isinstance(sender, dict) else str(sender)
            if sender_name:
                collaborator_counts[sender_name] = collaborator_counts.get(sender_name, 0) + 1
        
        # Sort by frequency
        key_collaborators = sorted(
            collaborator_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        # Extract findings (recent email snippets)
        findings = []
        seen_subjects = set()
        for email in (attendee_emails + topic_emails)[:10]:
            email_subject = email.get("subject", "")
            if email_subject not in seen_subjects:
                seen_subjects.add(email_subject)
                findings.append({
                    "subject": email_subject,
                    "from": email.get("from", {}).get("name", "") if isinstance(email.get("from"), dict) else str(email.get("from", "")),
                    "date": email.get("received", email.get("sent", "")),
                    "preview": email.get("bodyPreview", email.get("body", ""))[:150] + "..." if len(email.get("bodyPreview", email.get("body", ""))) > 150 else email.get("bodyPreview", email.get("body", "")),
                })
        
        return {
            "meeting": {
                "subject": subject,
                "time": start_time,
                "organizer": organizer,
                "attendees": attendee_names,
                "location": meeting.get("location", ""),
            },
            "agenda_keywords": keywords,
            "key_collaborators": [{"name": name, "email_count": count} for name, count in key_collaborators],
            "related_findings": findings[:5],
            "email_count": {
                "from_attendees": len(attendee_emails),
                "topic_related": len(topic_emails),
            },
        }
    
    def _extract_keywords(self, subject: str, body: str) -> List[str]:
        """Extract meaningful keywords from meeting subject and body."""
        # Common words to ignore
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "meeting", "call", "sync", "discussion", "review", "update", "weekly",
            "monthly", "daily", "team", "group", "re", "fwd", "fw"
        }
        
        # Combine and clean text
        text = f"{subject} {body}".lower()
        
        # Extract words
        import re
        words = re.findall(r'\b[a-z]{3,}\b', text)
        
        # Filter and dedupe
        keywords = []
        seen = set()
        for word in words:
            if word not in stopwords and word not in seen:
                seen.add(word)
                keywords.append(word)
        
        return keywords[:10]
    
    def _format_for_print(self, briefings: List[Dict], user: Dict, date: str, conflicts: List[Dict] = None) -> str:
        """Format briefings as printable text."""
        lines = [
            "=" * 60,
            f"DAILY BRIEFING - {date}",
            f"Prepared for: {user.get('name', 'Unknown')}",
            "=" * 60,
            "",
        ]
        
        # Show conflicts warning at top if any
        if conflicts:
            lines.extend([
                "⚠️  SCHEDULING CONFLICTS DETECTED:",
                "",
            ])
            for conflict in conflicts:
                lines.append(f"  ⚡ {conflict['meeting1'][:25]} vs {conflict['meeting2'][:25]}")
                lines.append(f"     Both at: {conflict['time1']}")
                
                # Show alternative contributors if available
                if conflict.get("alternatives1"):
                    lines.append(f"     → Possible delegates for '{conflict['meeting1'][:20]}':")
                    for alt in conflict["alternatives1"][:2]:
                        topics = ", ".join(alt.get("topics", [])[:2])
                        lines.append(f"       • {alt['name']} (discussed: {topics})")
                
                if conflict.get("alternatives2"):
                    lines.append(f"     → Possible delegates for '{conflict['meeting2'][:20]}':")
                    for alt in conflict["alternatives2"][:2]:
                        topics = ", ".join(alt.get("topics", [])[:2])
                        lines.append(f"       • {alt['name']} (discussed: {topics})")
                
                lines.append("")
            lines.extend(["-" * 60, ""])
        
        for i, briefing in enumerate(briefings, 1):
            meeting = briefing["meeting"]
            lines.extend([
                f"━━━ MEETING {i}: {meeting['subject'][:50]} ━━━",
                f"Time: {meeting['time']}",
                f"Organizer: {meeting['organizer']}",
                f"Attendees: {', '.join(meeting['attendees'][:5])}{'...' if len(meeting['attendees']) > 5 else ''}",
                f"Location: {meeting.get('location', 'Not specified')}",
                "",
            ])
            
            if briefing["key_collaborators"]:
                lines.append("KEY COLLABORATORS (recent email activity):")
                for collab in briefing["key_collaborators"][:3]:
                    lines.append(f"  • {collab['name']} ({collab['email_count']} emails)")
                lines.append("")
            
            if briefing["related_findings"]:
                lines.append("RECENT RELEVANT CONVERSATIONS:")
                for finding in briefing["related_findings"][:3]:
                    lines.extend([
                        f"  ▸ {finding['subject'][:45]}",
                        f"    From: {finding['from']} | {finding['date']}",
                        f"    {finding['preview'][:100]}...",
                        "",
                    ])
            
            if briefing["agenda_keywords"]:
                lines.append(f"TOPICS: {', '.join(briefing['agenda_keywords'][:6])}")
            
            lines.extend(["", "-" * 60, ""])
        
        lines.extend([
            "",
            f"Generated for informed meeting participation.",
            "=" * 60,
        ])
        
        return "\n".join(lines)


# Export all registered actions
REGISTERED_ACTIONS = registry
