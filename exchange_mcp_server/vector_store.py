"""
Vector Store for Exchange MCP
Uses ChromaDB for semantic search over emails and meetings.
Uses ChromaDB's built-in ONNX embedding function (no PyTorch required).
"""

import json
import hashlib
import logging
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

logger = logging.getLogger("exchange-mcp.vector_store")


class VectorStore:
    """ChromaDB-based vector store for semantic search."""
    
    def __init__(self, persist_path: str):
        self.persist_path = Path(persist_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with persistence
        # ChromaDB 0.4.x uses built-in ONNX embeddings by default
        self.client = chromadb.PersistentClient(
            path=str(self.persist_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collections - ChromaDB will use default embedding function
        self.emails_collection = self.client.get_or_create_collection(
            name="emails",
            metadata={"description": "Email documents for semantic search"}
        )
        
        self.meetings_collection = self.client.get_or_create_collection(
            name="meetings", 
            metadata={"description": "Meeting documents for semantic search"}
        )
        
        logger.info(f"VectorStore initialized at {persist_path}")
        logger.info(f"Emails: {self.emails_collection.count()}, Meetings: {self.meetings_collection.count()}")
    
    def needs_indexing(self) -> bool:
        """Check if documents need to be (re)indexed."""
        # If collections are empty, we need indexing
        if self.emails_collection.count() == 0:
            return True
        return False
    
    def get_indexed_ids(self, collection_type: str = "emails") -> set[str]:
        """Get the set of IDs already indexed in a collection."""
        collection = self.emails_collection if collection_type == "emails" else self.meetings_collection
        # Get all IDs from the collection
        try:
            results = collection.get(include=[])
            return set(results.get("ids", []))
        except Exception:
            return set()
    
    def index_new_documents(self, emails: list[dict], meetings: list[dict]) -> dict:
        """Index only new documents that aren't already in the vector store.
        Returns counts of newly indexed items."""
        
        indexed_email_ids = self.get_indexed_ids("emails")
        indexed_meeting_ids = self.get_indexed_ids("meetings")
        
        # Filter to only new documents
        new_emails = [e for e in emails if e.get("Id") not in indexed_email_ids]
        new_meetings = [m for m in meetings if m.get("Id") not in indexed_meeting_ids]
        
        if new_emails or new_meetings:
            logger.info(f"Indexing {len(new_emails)} new emails, {len(new_meetings)} new meetings...")
            self._index_emails(new_emails)
            self._index_meetings(new_meetings)
        
        return {
            "new_emails_indexed": len(new_emails),
            "new_meetings_indexed": len(new_meetings),
            "total_emails": self.emails_collection.count(),
            "total_meetings": self.meetings_collection.count()
        }
    
    def _index_emails(self, emails: list[dict]):
        """Index a list of emails."""
        if not emails:
            return
        
        batch_size = 50
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i+batch_size]
            docs = [f"Subject: {e.get('Subject', '')}\nFrom: {e.get('From', '')}\nBody: {e.get('Body', '')[:500]}" for e in batch]
            ids = [e.get("Id", str(i+j)) for j, e in enumerate(batch)]
            metas = [{
                "id": e.get("Id", ""),
                "subject": e.get("Subject", "")[:200],
                "from": e.get("From", ""),
                "to": e.get("To", "")[:200],
                "date": e.get("ReceivedDate", ""),
                "importance": e.get("Importance", "Normal")
            } for e in batch]
            
            self.emails_collection.add(documents=docs, ids=ids, metadatas=metas)
    
    def _index_meetings(self, meetings: list[dict]):
        """Index a list of meetings."""
        if not meetings:
            return
            
        batch_size = 50
        for i in range(0, len(meetings), batch_size):
            batch = meetings[i:i+batch_size]
            docs = [f"Subject: {m.get('Subject', '')}\nOrganizer: {m.get('Organizer', '')}\nLocation: {m.get('Location', '')}" for m in batch]
            ids = [m.get("Id", str(i+j)) for j, m in enumerate(batch)]
            metas = [{
                "id": m.get("Id", ""),
                "subject": m.get("Subject", "")[:200],
                "organizer": m.get("Organizer", ""),
                "location": m.get("Location", ""),
                "start": m.get("StartTime", ""),
                "end": m.get("EndTime", "")
            } for m in batch]
            
            self.meetings_collection.add(documents=docs, ids=ids, metadatas=metas)

    def index_documents(self, emails: list[dict], meetings: list[dict]):
        """Index emails and meetings into vector store. ChromaDB handles embeddings."""
        # Index emails
        if emails:
            logger.info(f"Indexing {len(emails)} emails...")
            batch_size = 50  # Smaller batches for stability
            for i in range(0, len(emails), batch_size):
                batch = emails[i:i+batch_size]
                docs = [f"Subject: {e.get('Subject', '')}\nFrom: {e.get('From', '')}\nBody: {e.get('Body', '')[:500]}" for e in batch]
                ids = [e.get("Id", str(i+j)) for j, e in enumerate(batch)]
                metas = [{
                    "id": e.get("Id", ""),
                    "subject": e.get("Subject", "")[:200],
                    "from": e.get("From", ""),
                    "to": e.get("To", "")[:200],
                    "date": e.get("ReceivedDate", ""),
                    "importance": e.get("Importance", "Normal")
                } for e in batch]
                
                self.emails_collection.add(documents=docs, ids=ids, metadatas=metas)
                logger.info(f"Indexed emails {i+1}-{min(i+batch_size, len(emails))} of {len(emails)}")
        
        # Index meetings
        if meetings:
            logger.info(f"Indexing {len(meetings)} meetings...")
            batch_size = 50
            for i in range(0, len(meetings), batch_size):
                batch = meetings[i:i+batch_size]
                docs = [f"Subject: {m.get('Subject', '')}\nOrganizer: {m.get('Organizer', '')}\nLocation: {m.get('Location', '')}" for m in batch]
                ids = [m.get("Id", str(i+j)) for j, m in enumerate(batch)]
                metas = [{
                    "id": m.get("Id", ""),
                    "subject": m.get("Subject", "")[:200],
                    "organizer": m.get("Organizer", ""),
                    "location": m.get("Location", ""),
                    "start": m.get("StartTime", ""),
                    "end": m.get("EndTime", "")
                } for m in batch]
                
                self.meetings_collection.add(documents=docs, ids=ids, metadatas=metas)
                logger.info(f"Indexed meetings {i+1}-{min(i+batch_size, len(meetings))} of {len(meetings)}")
    
    def search_emails(self, query: str, limit: int = 10) -> list[dict]:
        """Search emails using semantic similarity."""
        results = self.emails_collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        # Format results
        output = []
        if results and results.get("metadatas") and results["metadatas"][0]:
            for i, metadata in enumerate(results["metadatas"][0]):
                distance = results["distances"][0][i] if results.get("distances") else 0
                output.append({
                    "id": metadata.get("id"),
                    "subject": metadata.get("subject"),
                    "from": metadata.get("from"),
                    "to": metadata.get("to"),
                    "date": metadata.get("date"),
                    "importance": metadata.get("importance"),
                    "relevance_score": round(1 - distance, 3) if distance else 1.0
                })
        
        return output
    
    def search_meetings(self, query: str, limit: int = 10) -> list[dict]:
        """Search meetings using semantic similarity."""
        results = self.meetings_collection.query(
            query_texts=[query],
            n_results=limit
        )
        
        # Format results
        output = []
        if results and results.get("metadatas") and results["metadatas"][0]:
            for i, metadata in enumerate(results["metadatas"][0]):
                distance = results["distances"][0][i] if results.get("distances") else 0
                output.append({
                    "id": metadata.get("id"),
                    "subject": metadata.get("subject"),
                    "organizer": metadata.get("organizer"),
                    "location": metadata.get("location"),
                    "start": metadata.get("start"),
                    "end": metadata.get("end"),
                    "relevance_score": round(1 - distance, 3) if distance else 1.0
                })
        
        return output
    
    def clear(self):
        """Clear all indexed documents."""
        self.client.delete_collection("emails")
        self.client.delete_collection("meetings")
        
        self.emails_collection = self.client.get_or_create_collection(name="emails")
        self.meetings_collection = self.client.get_or_create_collection(name="meetings")
