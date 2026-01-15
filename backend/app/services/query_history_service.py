import json
import numpy as np
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.query_history import QueryHistory
from app.core.llms import get_default_embedding_model

class QueryHistoryService:
    def __init__(self, db: Session):
        self.db = db
        try:
            self.embedding_model = get_default_embedding_model()
        except Exception as e:
            print(f"Warning: Could not initialize embedding model: {e}")
            self.embedding_model = None

    def save_query(self, query_text: str, connection_id: int, meta_info: Dict[str, Any] = None):
        """Save a user query with its embedding."""
        embedding = []
        if self.embedding_model:
            try:
                embedding = self.embedding_model.embed_query(query_text)
            except Exception as e:
                print(f"Error generating embedding: {e}")
        
        history = QueryHistory(
            query_text=query_text,
            embedding=embedding,
            connection_id=connection_id,
            meta_info=meta_info
        )
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def find_similar_queries(self, query_text: str, limit: int = 5, threshold: float = 0.7) -> List[QueryHistory]:
        """Find similar queries using cosine similarity."""
        if not self.embedding_model:
            return []

        try:
            target_embedding = self.embedding_model.embed_query(query_text)
            
            # Fetch all history (naive implementation for small dataset)
            # In production, use a Vector DB or PGVector
            history_items = self.db.query(QueryHistory).filter(QueryHistory.embedding.isnot(None)).all()
            
            results = []
            for item in history_items:
                if not item.embedding:
                    continue
                
                # Calculate cosine similarity
                item_embedding = item.embedding
                if isinstance(item_embedding, str):
                    item_embedding = json.loads(item_embedding)
                
                similarity = self._cosine_similarity(target_embedding, item_embedding)
                
                if similarity >= threshold:
                    results.append((similarity, item))
            
            # Sort by similarity desc
            results.sort(key=lambda x: x[0], reverse=True)
            
            return [item for _, item in results[:limit]]
            
        except Exception as e:
            print(f"Error searching similar queries: {e}")
            return []

    def _cosine_similarity(self, v1, v2):
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        return dot_product / (norm_v1 * norm_v2)
