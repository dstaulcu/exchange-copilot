# User Guide

This guide explains how to use the Exchange MCP Assistant to interact with your email, calendar, and colleague directory.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Chat Interface Overview](#chat-interface-overview)
3. [Example Queries](#example-queries)
4. [Understanding Responses](#understanding-responses)
5. [Tips for Best Results](#tips-for-best-results)

---

## Getting Started

### Starting the Application

1. Open PowerShell in the project directory
2. Run the startup script:

```powershell
.\Start-App.ps1
```

3. Your browser will automatically open to `http://127.0.0.1:8000`

### First Launch

On first launch, the system will:
1. Load your Exchange data (mock data or real, depending on configuration)
2. Index emails and meetings for semantic search (may take 1-2 minutes)
3. Connect to the LLM (Ollama or OpenAI)

You'll see the chat interface with a sidebar showing your status.

---

## Chat Interface Overview

### Main Components

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌─────────────┐  ┌──────────────────────────────────────────┐  │
│  │             │  │                                          │  │
│  │  Sidebar    │  │           Chat Messages                  │  │
│  │             │  │                                          │  │
│  │  - User     │  │  Shows conversation history with         │  │
│  │    Info     │  │  the AI assistant                        │  │
│  │             │  │                                          │  │
│  │  - Status   │  │                                          │  │
│  │    Cards    │  │                                          │  │
│  │             │  │                                          │  │
│  │  - Quick    │  ├──────────────────────────────────────────┤  │
│  │    Actions  │  │  Type your message here...         Send  │  │
│  │             │  │                                          │  │
│  └─────────────┘  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Sidebar Elements

| Element | Description |
|---------|-------------|
| **User Info** | Shows your name and email |
| **Unread Emails** | Count of unread emails (click to ask about them) |
| **Meetings Today** | Number of meetings today (click for details) |
| **Sync Button** | Manually trigger data refresh |
| **Quick Actions** | Pre-built queries for common tasks |

### Quick Actions

Click these buttons to run common queries:

- **📧 Check Inbox** - View recent unread emails
- **📅 Today's Meetings** - See your schedule for today
- **📊 My Stats** - Get email and meeting statistics
- **👥 My Team** - List colleagues in your department

---

## Example Queries

### Email Queries

| Query | What It Does |
|-------|--------------|
| "Show my unread emails" | Lists unread inbox messages |
| "What emails did I get from John?" | Searches for emails from John |
| "Find emails about the Q4 report" | Semantic search for Q4 report emails |
| "Read email [ID]" | Shows full content of a specific email |
| "How many emails did I receive this week?" | Email statistics |
| "Who sends me the most emails?" | Top senders analysis |

### Calendar Queries

| Query | What It Does |
|-------|--------------|
| "What meetings do I have today?" | Today's schedule |
| "Show my calendar for this week" | Next 7 days of meetings |
| "When is my next meeting with Sarah?" | Searches for meetings with Sarah |
| "Find meetings about budget planning" | Semantic search for budget meetings |
| "How many meetings do I have this month?" | Meeting statistics |

### Colleague Queries

| Query | What It Does |
|-------|--------------|
| "Find John Smith" | Search for a colleague |
| "Who works in Engineering?" | List department members |
| "What's Sarah's email address?" | Get contact information |
| "Show the org structure" | Department breakdown |

### Combined Queries

| Query | What It Does |
|-------|--------------|
| "Do I have any urgent emails or meetings today?" | Overview of priorities |
| "What's happening with the Alpha project?" | Searches emails and meetings |
| "Summarize my week" | Stats and highlights |

---

## Understanding Responses

### Email Listings

When the assistant shows emails, you'll see:

```
📧 Inbox (3 unread of 15 total)

1. **Budget Review** - From: Jane Doe
   Received: 2026-02-05 09:30 AM
   ⚠️ Unread | 🔴 High Importance
   ID: email-123

2. **Team Standup Notes** - From: Mike Wilson
   Received: 2026-02-05 08:15 AM
   ID: email-456
```

- **⚠️ Unread** - Email hasn't been read
- **🔴 High Importance** - Marked as high priority
- **ID** - Use this to read the full email: "Read email email-123"

### Meeting Listings

```
📅 Today's Meetings (3)

1. **Sprint Planning** - 10:00 AM - 11:00 AM
   Location: Conference Room A
   Organizer: Sarah Chen
   Attendees: You + 4 others

2. **1:1 with Manager** - 2:00 PM - 2:30 PM
   Location: Office 302
```

### Search Results

Semantic search returns results ranked by relevance:

```
🔍 Search Results for "Q4 budget"

1. [94% match] **Q4 Budget Proposal** (email)
   From: Finance Team - 2026-01-28
   Preview: "Please review the attached Q4 budget..."

2. [87% match] **Quarterly Planning** (meeting)
   Date: 2026-01-25
   Preview: "Discuss Q4 budget allocation..."
```

---

## Tips for Best Results

### Be Specific

❌ "Show emails"
✅ "Show my unread emails from this week"

❌ "Find meeting"
✅ "Find my next meeting with the marketing team"

### Use Natural Language

The assistant understands natural language. These all work:

- "What's on my calendar tomorrow?"
- "Any emails from the CEO?"
- "Who's in my department?"
- "Tell me about meetings next week"

### Ask Follow-up Questions

The assistant maintains context within a conversation:

1. You: "Show my unread emails"
2. Assistant: *shows 5 emails*
3. You: "Read the first one"
4. Assistant: *shows full email content*

### Use Search for Discovery

When you're not sure what you're looking for:

- "Find anything about Project Alpha"
- "Search for emails mentioning deadline"
- "Look for meetings about training"

### Check Statistics

Get an overview before diving into details:

- "Give me my email stats"
- "How busy is my calendar this week?"
- "Summary of my inbox"

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line in message |
| `Ctrl+/` | Focus on input field |

---

## Troubleshooting

### "I couldn't find any results"

- Try broader search terms
- Check spelling of names
- Use semantic search: "Find emails about [topic]"

### Slow Responses

- First query may be slow (model loading)
- Large searches take longer
- Check Ollama is running: `ollama list`

### "Tool call failed"

- Data may not be loaded
- Click "Sync" in sidebar to refresh
- Check server logs for errors

### Interface Not Loading

- Verify server is running (check terminal)
- Try refreshing the browser
- Check http://127.0.0.1:8000/api/health

---

## Privacy Notes

- All processing happens locally (when using Ollama)
- No data is sent to external servers (in mock/Ollama mode)
- Chat history is not persisted (cleared on refresh)
- Vector embeddings are stored locally only

---

## Next Steps

- [Setup Guide](SETUP_GUIDE.md) - Installation and configuration
- [Admin Guide](ADMIN_GUIDE.md) - Advanced configuration
