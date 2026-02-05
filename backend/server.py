#!/usr/bin/env python3
"""
FastAPI Backend Server for Exchange MCP Assistant.

Provides:
- REST API for chat interactions
- WebSocket for streaming responses  
- Background task for periodic data sync
- Health/status endpoints
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exchange_mcp_server import server as mcp_server
from backend.chat_engine import ChatEngine
from backend.interaction_log import (
    get_interaction_store,
    create_interaction_log,
    InteractionStore,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("exchange-backend")


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Server configuration."""
    # Server settings
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    # LLM Provider settings
    # Options: "ollama" (local) or "openai" (OpenAI-compatible API)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    LLM_MODEL: str = os.getenv("LLM_MODEL", os.getenv("OLLAMA_MODEL", "llama3.2"))
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")
    
    # Sync settings
    SYNC_INTERVAL_MINUTES: int = int(os.getenv("SYNC_INTERVAL_MINUTES", "5"))
    
    # Data source settings
    DATA_SOURCE: str = os.getenv("DATA_SOURCE", "mock")
    DATA_PATH: str = os.getenv("DATA_PATH", "data")
    DATA_FILE: str = os.getenv("DATA_FILE", os.path.join(DATA_PATH, "exchange_mcp.json"))
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", os.path.join(DATA_PATH, "chroma_db"))
    
    # Microsoft Graph API settings
    GRAPH_TENANT_ID: str = os.getenv("GRAPH_TENANT_ID", "")
    GRAPH_CLIENT_ID: str = os.getenv("GRAPH_CLIENT_ID", "")
    GRAPH_CLIENT_SECRET: str = os.getenv("GRAPH_CLIENT_SECRET", "")
    GRAPH_USER_EMAIL: str = os.getenv("GRAPH_USER_EMAIL", "")
    
    # Exchange Web Services settings
    EWS_SERVER: str = os.getenv("EWS_SERVER", "")
    EWS_EMAIL: str = os.getenv("EWS_EMAIL", "")
    EWS_USERNAME: str = os.getenv("EWS_USERNAME", "")
    EWS_PASSWORD: str = os.getenv("EWS_PASSWORD", "")
    EWS_AUTODISCOVER: bool = os.getenv("EWS_AUTODISCOVER", "true").lower() == "true"
    
    @classmethod
    def get_data_source_config(cls) -> dict:
        """Get configuration dict for the data source."""
        if cls.DATA_SOURCE == "graph":
            return {
                "tenant_id": cls.GRAPH_TENANT_ID,
                "client_id": cls.GRAPH_CLIENT_ID,
                "client_secret": cls.GRAPH_CLIENT_SECRET,
                "user_email": cls.GRAPH_USER_EMAIL,
            }
        elif cls.DATA_SOURCE == "ews":
            return {
                "server": cls.EWS_SERVER,
                "email": cls.EWS_EMAIL,
                "username": cls.EWS_USERNAME,
                "password": cls.EWS_PASSWORD,
                "autodiscover": cls.EWS_AUTODISCOVER,
            }
        else:  # mock
            return {"cache_path": cls.DATA_FILE}
    
    @classmethod
    def get_vector_store_config(cls) -> dict:
        """Get configuration dict for the vector store."""
        return {
            "chroma_db_path": cls.CHROMA_DB_PATH,
        }
    
    @classmethod
    def get_llm_config(cls) -> dict:
        """Get configuration dict for the LLM."""
        return {
            "provider": cls.LLM_PROVIDER,
            "model": cls.LLM_MODEL,
            "api_key": cls.LLM_API_KEY,
            "base_url": cls.LLM_BASE_URL,
        }


config = Config()


# ============================================================================
# Background Sync Task
# ============================================================================

class SyncManager:
    """Manages periodic data synchronization."""
    
    def __init__(self, interval_minutes: int = 5):
        self.interval_minutes = interval_minutes
        self.last_sync: Optional[datetime] = None
        self.sync_count: int = 0
        self.is_running: bool = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the background sync task."""
        if self._task is None:
            self.is_running = True
            self._task = asyncio.create_task(self._sync_loop())
            logger.info(f"Sync manager started (interval: {self.interval_minutes} min)")
    
    async def stop(self):
        """Stop the background sync task."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("Sync manager stopped")
    
    async def _sync_loop(self):
        """Background loop that syncs data periodically."""
        while self.is_running:
            try:
                await asyncio.sleep(self.interval_minutes * 60)
                await self.sync_now()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync error: {e}")
    
    async def sync_now(self) -> dict:
        """Perform an immediate sync."""
        logger.info("Starting data sync...")
        try:
            # Run sync in thread pool (it's blocking IO)
            result = await asyncio.to_thread(mcp_server.sync_data)
            self.last_sync = datetime.now()
            self.sync_count += 1
            logger.info(f"Sync complete: {result}")
            return result
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return {"error": str(e)}
    
    def get_status(self) -> dict:
        """Get sync manager status."""
        return {
            "is_running": self.is_running,
            "interval_minutes": self.interval_minutes,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "sync_count": self.sync_count
        }


# Global instances
sync_manager = SyncManager(interval_minutes=config.SYNC_INTERVAL_MINUTES)
chat_engine: Optional[ChatEngine] = None


# ============================================================================
# FastAPI App with Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global chat_engine
    
    # Startup
    logger.info("Starting Exchange MCP Backend...")
    logger.info(f"Data source: {config.DATA_SOURCE}")
    logger.info(f"LLM provider: {config.LLM_PROVIDER}")
    logger.info(f"Data path: {config.DATA_PATH}")
    logger.info(f"ChromaDB path: {config.CHROMA_DB_PATH}")
    
    # Initialize MCP server with configured data source
    source_config = config.get_data_source_config()
    vector_config = config.get_vector_store_config()
    mcp_server.initialize(
        source_type=config.DATA_SOURCE,
        chroma_db_path=vector_config["chroma_db_path"],
        **source_config
    )
    logger.info("MCP server initialized")
    
    # Initialize chat engine with configured LLM
    llm_config = config.get_llm_config()
    chat_engine = ChatEngine(**llm_config)
    
    # Start sync manager
    await sync_manager.start()
    
    yield
    
    # Shutdown
    await sync_manager.stop()
    logger.info("Backend shutdown complete")


app = FastAPI(
    title="Exchange MCP Backend",
    description="Backend API for Exchange email/calendar assistant",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    session_id: Optional[str] = None
    
class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    tools_used: list[str] = []
    interaction_id: Optional[str] = None  # For feedback reference

class SyncResponse(BaseModel):
    """Sync response model."""
    new_emails_indexed: int = 0
    new_meetings_indexed: int = 0
    total_emails: int = 0
    total_meetings: int = 0
    error: Optional[str] = None


class FeedbackRequest(BaseModel):
    """Feedback request model."""
    interaction_id: str
    rating: int  # 1 = thumbs up, -1 = thumbs down, 0 = neutral
    comment: Optional[str] = None
    categories: Optional[list[str]] = None  # speed, quality, accuracy


class FeedbackResponse(BaseModel):
    """Feedback response model."""
    success: bool
    message: str


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Redirect to frontend."""
    index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")
    return FileResponse(index_path)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/status")
async def status():
    """Get system status including user info, stats, and sync status."""
    data_loader = mcp_server.data_source
    me = data_loader.get_me()
    
    return {
        "user": {
            "name": me.get("DisplayName"),
            "email": me.get("Email"),
            "department": me.get("Department"),
            "title": me.get("JobTitle")
        },
        "stats": {
            "unread_emails": data_loader.get_unread_count(),
            "meetings_today": len(data_loader.get_todays_meetings()),
            "total_emails": data_loader.get_email_stats().get("total", 0),
            "total_meetings": data_loader.get_meeting_stats().get("total", 0)
        },
        "sync": sync_manager.get_status(),
        "model": f"{config.LLM_PROVIDER}:{config.LLM_MODEL}"
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a chat message and get a response."""
    import time
    
    if not chat_engine:
        raise HTTPException(status_code=503, detail="Chat engine not initialized")
    
    start_time = time.perf_counter()
    
    try:
        response, tools_used = await asyncio.to_thread(
            chat_engine.chat, request.message
        )
        
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Log the interaction
        interaction_log = create_interaction_log(
            user_query=request.message,
            response=response,
            tools_used=[{"name": t} for t in tools_used],
            model_provider=config.LLM_PROVIDER,
            model_name=config.LLM_MODEL,
            duration_ms=duration_ms,
            session_id=request.session_id,
        )
        
        store = get_interaction_store()
        interaction_id = store.log_interaction(interaction_log)
        
        return ChatResponse(
            response=response,
            tools_used=tools_used,
            interaction_id=interaction_id
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync", response_model=SyncResponse)
async def trigger_sync():
    """Manually trigger a data sync."""
    result = await sync_manager.sync_now()
    return SyncResponse(**result)


# ============================================================================
# Feedback API Endpoints
# ============================================================================

@app.post("/api/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """Submit feedback for an interaction."""
    store = get_interaction_store()
    
    success = store.add_feedback(
        interaction_id=request.interaction_id,
        rating=request.rating,
        comment=request.comment,
        categories=request.categories
    )
    
    if success:
        return FeedbackResponse(
            success=True,
            message="Feedback recorded successfully"
        )
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Interaction not found: {request.interaction_id}"
        )


@app.get("/api/feedback/stats")
async def get_feedback_stats():
    """Get aggregate feedback statistics."""
    store = get_interaction_store()
    return store.get_feedback_stats()


@app.get("/api/feedback/recent")
async def get_recent_interactions(limit: int = 50):
    """Get recent interactions with their feedback status."""
    store = get_interaction_store()
    interactions = store.get_recent(limit=limit)
    return {
        "count": len(interactions),
        "interactions": [i.to_dict() for i in interactions]
    }


@app.get("/api/feedback/negative")
async def get_negative_feedback(limit: int = 20):
    """Get interactions with negative feedback for review."""
    store = get_interaction_store()
    interactions = store.get_negative_feedback(limit=limit)
    return {
        "count": len(interactions),
        "interactions": [i.to_dict() for i in interactions]
    }


@app.get("/api/feedback/{interaction_id}")
async def get_interaction(interaction_id: str):
    """Get details of a specific interaction."""
    store = get_interaction_store()
    interaction = store.get_interaction(interaction_id)
    
    if interaction:
        return interaction.to_dict()
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Interaction not found: {interaction_id}"
        )


@app.get("/api/inbox")
async def get_inbox(limit: int = 10, unread_only: bool = False):
    """Get inbox emails."""
    data_loader = mcp_server.data_source
    emails = data_loader.get_inbox(limit=limit, unread_only=unread_only)
    return {
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
                "preview": e.get("Body", "")[:150]
            }
            for e in emails
        ]
    }


@app.get("/api/calendar")
async def get_calendar(days: int = 7):
    """Get upcoming meetings."""
    data_loader = mcp_server.data_source
    meetings = data_loader.get_calendar(days=days)
    return {
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
    }


@app.get("/api/meetings/today")
async def get_todays_meetings():
    """Get today's meetings."""
    data_loader = mcp_server.data_source
    meetings = data_loader.get_todays_meetings()
    return {
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
    }


# ============================================================================
# WebSocket for Streaming Chat
# ============================================================================

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for streaming chat."""
    import time
    
    await websocket.accept()
    logger.info("WebSocket client connected")
    
    session_id = None
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "chat":
                user_message = message.get("content", "")
                session_id = message.get("session_id", session_id)
                
                # Send "thinking" status
                await websocket.send_json({"type": "status", "content": "thinking"})
                
                start_time = time.perf_counter()
                
                # Get response
                try:
                    response, tools_used = await asyncio.to_thread(
                        chat_engine.chat, user_message
                    )
                    
                    duration_ms = (time.perf_counter() - start_time) * 1000
                    
                    # Log the interaction
                    interaction_log = create_interaction_log(
                        user_query=user_message,
                        response=response,
                        tools_used=[{"name": t} for t in tools_used],
                        model_provider=config.LLM_PROVIDER,
                        model_name=config.LLM_MODEL,
                        duration_ms=duration_ms,
                        session_id=session_id,
                    )
                    
                    store = get_interaction_store()
                    interaction_id = store.log_interaction(interaction_log)
                    
                    await websocket.send_json({
                        "type": "response",
                        "content": response,
                        "tools_used": tools_used,
                        "interaction_id": interaction_id
                    })
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "content": str(e)
                    })
            
            elif message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")


# ============================================================================
# Static Files (Frontend)
# ============================================================================

# Get frontend path
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


@app.get("/dashboard.html")
@app.get("/dashboard")
async def dashboard():
    """Serve the feedback dashboard."""
    dashboard_path = os.path.join(frontend_path, "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"error": "Dashboard not found", "path": dashboard_path}


# Mount frontend static files AFTER explicit routes
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the server."""
    import uvicorn
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           Exchange MCP Backend Server                       ║
╠══════════════════════════════════════════════════════════════╣
║  Host:          http://{config.HOST}:{config.PORT}                       ║
║  LLM:           {config.LLM_PROVIDER}:{config.LLM_MODEL:<15}                 ║
║  Sync Interval: {config.SYNC_INTERVAL_MINUTES} minutes                                   ║
║  Debug:         {str(config.DEBUG):<5}                                      ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "backend.server:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info"
    )


if __name__ == "__main__":
    main()
