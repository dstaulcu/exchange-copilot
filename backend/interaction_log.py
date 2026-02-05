"""
Interaction Logging System - Track all agent interactions for feedback loops.

This module provides:
- Structured logging of all chat interactions
- Tool call tracing with inputs/outputs
- Feedback association (thumbs up/down)
- Export for analysis and training
"""

import json
import logging
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("exchange-backend.interaction_log")


@dataclass
class ToolCallLog:
    """Record of a single tool invocation."""
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class InteractionLog:
    """Complete record of a user interaction."""
    interaction_id: str
    session_id: str
    timestamp: str
    
    # Input
    user_query: str
    
    # Model info
    model_provider: str
    model_name: str
    
    # Output
    response: str
    tool_calls: List[ToolCallLog]
    
    # Timing
    total_duration_ms: float
    
    # Feedback (set later)
    feedback_rating: Optional[int] = None  # 1 = thumbs up, -1 = thumbs down, 0 = neutral
    feedback_comment: Optional[str] = None
    feedback_categories: Optional[List[str]] = None  # speed, quality, accuracy, etc.
    feedback_timestamp: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d["tool_calls"] = [asdict(tc) for tc in self.tool_calls]
        return d


class InteractionStore:
    """
    SQLite-based storage for interaction logs.
    
    Thread-safe and supports:
    - Append-only interaction logging
    - Feedback updates
    - Queries for analysis
    - Export to JSON/CSV
    """
    
    def __init__(self, db_path: str | Path | None = None):
        """
        Initialize the interaction store.
        
        Args:
            db_path: Path to SQLite database. Defaults to data/interactions.db
        """
        if db_path is None:
            data_path = os.getenv("DATA_PATH", "data")
            db_path = os.path.join(data_path, "interactions.db")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._local = threading.local()
        self._init_schema()
        
        logger.info(f"InteractionStore initialized at {self.db_path}")
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    @contextmanager
    def _transaction(self):
        """Context manager for database transactions."""
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def _init_schema(self):
        """Initialize database schema."""
        with self._transaction() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS interactions (
                    interaction_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_query TEXT NOT NULL,
                    model_provider TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    response TEXT NOT NULL,
                    total_duration_ms REAL NOT NULL,
                    feedback_rating INTEGER,
                    feedback_comment TEXT,
                    feedback_categories TEXT,
                    feedback_timestamp TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interaction_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    duration_ms REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (interaction_id) REFERENCES interactions(interaction_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_interactions_session 
                    ON interactions(session_id);
                CREATE INDEX IF NOT EXISTS idx_interactions_timestamp 
                    ON interactions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_interactions_feedback 
                    ON interactions(feedback_rating);
                CREATE INDEX IF NOT EXISTS idx_tool_calls_interaction 
                    ON tool_calls(interaction_id);
                CREATE INDEX IF NOT EXISTS idx_tool_calls_name 
                    ON tool_calls(tool_name);
            """)
    
    def log_interaction(self, interaction: InteractionLog) -> str:
        """
        Log a new interaction.
        
        Args:
            interaction: The interaction to log
            
        Returns:
            The interaction_id
        """
        with self._transaction() as conn:
            conn.execute("""
                INSERT INTO interactions (
                    interaction_id, session_id, timestamp, user_query,
                    model_provider, model_name, response, total_duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                interaction.interaction_id,
                interaction.session_id,
                interaction.timestamp,
                interaction.user_query,
                interaction.model_provider,
                interaction.model_name,
                interaction.response,
                interaction.total_duration_ms,
            ))
            
            for tc in interaction.tool_calls:
                conn.execute("""
                    INSERT INTO tool_calls (
                        interaction_id, tool_name, arguments, result,
                        error, duration_ms, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    interaction.interaction_id,
                    tc.tool_name,
                    json.dumps(tc.arguments),
                    tc.result,
                    tc.error,
                    tc.duration_ms,
                    tc.timestamp,
                ))
        
        logger.debug(f"Logged interaction {interaction.interaction_id}")
        return interaction.interaction_id
    
    def add_feedback(
        self,
        interaction_id: str,
        rating: int,
        comment: Optional[str] = None,
        categories: Optional[List[str]] = None
    ) -> bool:
        """
        Add feedback to an interaction.
        
        Args:
            interaction_id: The interaction to update
            rating: 1 (thumbs up), -1 (thumbs down), 0 (neutral)
            comment: Optional feedback comment
            categories: Optional list of feedback categories (speed, quality, accuracy)
            
        Returns:
            True if successful, False if interaction not found
        """
        timestamp = datetime.utcnow().isoformat()
        categories_json = json.dumps(categories) if categories else None
        
        with self._transaction() as conn:
            cursor = conn.execute("""
                UPDATE interactions 
                SET feedback_rating = ?, 
                    feedback_comment = ?,
                    feedback_categories = ?,
                    feedback_timestamp = ?
                WHERE interaction_id = ?
            """, (rating, comment, categories_json, timestamp, interaction_id))
            
            if cursor.rowcount == 0:
                return False
        
        logger.info(f"Feedback added to {interaction_id}: rating={rating}, categories={categories}")
        return True
    
    def get_interaction(self, interaction_id: str) -> Optional[InteractionLog]:
        """Get a single interaction by ID."""
        conn = self._get_conn()
        
        row = conn.execute(
            "SELECT * FROM interactions WHERE interaction_id = ?",
            (interaction_id,)
        ).fetchone()
        
        if not row:
            return None
        
        tool_calls = conn.execute(
            "SELECT * FROM tool_calls WHERE interaction_id = ? ORDER BY timestamp",
            (interaction_id,)
        ).fetchall()
        
        return self._row_to_interaction(row, tool_calls)
    
    def get_recent(self, limit: int = 50) -> List[InteractionLog]:
        """Get recent interactions."""
        conn = self._get_conn()
        
        rows = conn.execute(
            "SELECT * FROM interactions ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        
        interactions = []
        for row in rows:
            tool_calls = conn.execute(
                "SELECT * FROM tool_calls WHERE interaction_id = ?",
                (row["interaction_id"],)
            ).fetchall()
            interactions.append(self._row_to_interaction(row, tool_calls))
        
        return interactions
    
    def get_by_session(self, session_id: str) -> List[InteractionLog]:
        """Get all interactions for a session."""
        conn = self._get_conn()
        
        rows = conn.execute(
            "SELECT * FROM interactions WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        ).fetchall()
        
        interactions = []
        for row in rows:
            tool_calls = conn.execute(
                "SELECT * FROM tool_calls WHERE interaction_id = ?",
                (row["interaction_id"],)
            ).fetchall()
            interactions.append(self._row_to_interaction(row, tool_calls))
        
        return interactions
    
    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get aggregate feedback statistics."""
        conn = self._get_conn()
        
        stats = conn.execute("""
            SELECT 
                COUNT(*) as total_interactions,
                SUM(CASE WHEN feedback_rating IS NOT NULL THEN 1 ELSE 0 END) as rated_count,
                SUM(CASE WHEN feedback_rating = 1 THEN 1 ELSE 0 END) as thumbs_up,
                SUM(CASE WHEN feedback_rating = -1 THEN 1 ELSE 0 END) as thumbs_down,
                SUM(CASE WHEN feedback_rating = 0 THEN 1 ELSE 0 END) as neutral,
                AVG(total_duration_ms) as avg_duration_ms
            FROM interactions
        """).fetchone()
        
        tool_stats = conn.execute("""
            SELECT 
                tool_name,
                COUNT(*) as call_count,
                AVG(duration_ms) as avg_duration_ms,
                SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) as error_count
            FROM tool_calls
            GROUP BY tool_name
            ORDER BY call_count DESC
        """).fetchall()
        
        # Count feedback categories
        category_rows = conn.execute("""
            SELECT feedback_categories FROM interactions 
            WHERE feedback_categories IS NOT NULL AND feedback_categories != ''
        """).fetchall()
        
        category_counts = {"speed": 0, "quality": 0, "accuracy": 0}
        for row in category_rows:
            try:
                categories = json.loads(row["feedback_categories"])
                for cat in categories:
                    if cat in category_counts:
                        category_counts[cat] += 1
            except (json.JSONDecodeError, TypeError):
                pass
        
        return {
            "total_interactions": stats["total_interactions"],
            "rated_count": stats["rated_count"],
            "thumbs_up": stats["thumbs_up"],
            "thumbs_down": stats["thumbs_down"],
            "neutral": stats["neutral"],
            "approval_rate": (
                stats["thumbs_up"] / stats["rated_count"] * 100
                if stats["rated_count"] > 0 else 0
            ),
            "avg_duration_ms": stats["avg_duration_ms"],
            "category_counts": category_counts,
            "tool_usage": [
                {
                    "tool_name": row["tool_name"],
                    "call_count": row["call_count"],
                    "avg_duration_ms": row["avg_duration_ms"],
                    "error_rate": row["error_count"] / row["call_count"] * 100 if row["call_count"] > 0 else 0,
                }
                for row in tool_stats
            ],
        }
    
    def get_negative_feedback(self, limit: int = 20) -> List[InteractionLog]:
        """Get interactions with negative feedback for review."""
        conn = self._get_conn()
        
        rows = conn.execute(
            "SELECT * FROM interactions WHERE feedback_rating = -1 ORDER BY feedback_timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        
        interactions = []
        for row in rows:
            tool_calls = conn.execute(
                "SELECT * FROM tool_calls WHERE interaction_id = ?",
                (row["interaction_id"],)
            ).fetchall()
            interactions.append(self._row_to_interaction(row, tool_calls))
        
        return interactions
    
    def export_to_json(self, filepath: str | Path, limit: int = None):
        """Export interactions to JSON file."""
        interactions = self.get_recent(limit) if limit else self.get_recent(10000)
        
        with open(filepath, "w") as f:
            json.dump(
                [i.to_dict() for i in interactions],
                f,
                indent=2
            )
        
        logger.info(f"Exported {len(interactions)} interactions to {filepath}")
    
    def _row_to_interaction(self, row, tool_call_rows) -> InteractionLog:
        """Convert database rows to InteractionLog."""
        tool_calls = [
            ToolCallLog(
                tool_name=tc["tool_name"],
                arguments=json.loads(tc["arguments"]),
                result=tc["result"],
                error=tc["error"],
                duration_ms=tc["duration_ms"],
                timestamp=tc["timestamp"],
            )
            for tc in tool_call_rows
        ]
        
        # Parse feedback categories if present
        categories = None
        try:
            if row["feedback_categories"]:
                categories = json.loads(row["feedback_categories"])
        except (json.JSONDecodeError, KeyError):
            pass
        
        return InteractionLog(
            interaction_id=row["interaction_id"],
            session_id=row["session_id"],
            timestamp=row["timestamp"],
            user_query=row["user_query"],
            model_provider=row["model_provider"],
            model_name=row["model_name"],
            response=row["response"],
            tool_calls=tool_calls,
            total_duration_ms=row["total_duration_ms"],
            feedback_rating=row["feedback_rating"],
            feedback_comment=row["feedback_comment"],
            feedback_categories=categories,
            feedback_timestamp=row["feedback_timestamp"],
        )


# Global instance (lazy initialization)
_store: Optional[InteractionStore] = None


def get_interaction_store() -> InteractionStore:
    """Get the global interaction store instance."""
    global _store
    if _store is None:
        _store = InteractionStore()
    return _store


def create_interaction_log(
    user_query: str,
    response: str,
    tools_used: List[Dict[str, Any]],
    model_provider: str,
    model_name: str,
    duration_ms: float,
    session_id: str = None,
) -> InteractionLog:
    """
    Helper to create an InteractionLog from chat results.
    
    Args:
        user_query: The user's input
        response: The assistant's response
        tools_used: List of tool call records
        model_provider: LLM provider name
        model_name: Model name
        duration_ms: Total response time
        session_id: Optional session ID (generated if not provided)
    """
    tool_calls = [
        ToolCallLog(
            tool_name=tc.get("name", tc.get("tool_name", "unknown")),
            arguments=tc.get("arguments", tc.get("args", {})),
            result=tc.get("result"),
            error=tc.get("error"),
            duration_ms=tc.get("duration_ms", 0),
        )
        for tc in tools_used
    ]
    
    return InteractionLog(
        interaction_id=str(uuid.uuid4())[:12],
        session_id=session_id or str(uuid.uuid4())[:8],
        timestamp=datetime.utcnow().isoformat(),
        user_query=user_query,
        response=response,
        tool_calls=tool_calls,
        model_provider=model_provider,
        model_name=model_name,
        total_duration_ms=duration_ms,
    )
