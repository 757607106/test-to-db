import json
import numpy as np
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.query_history import QueryHistory
from app.core.llms import get_default_embedding_model

class QueryHistoryService:
    """
    查询历史服务 - 支持多租户数据隔离
    
    所有查询和保存操作都需要指定 tenant_id 以确保数据隔离。
    """
    
    def __init__(self, db: Session):
        self.db = db
        try:
            self.embedding_model = get_default_embedding_model()
        except Exception as e:
            print(f"Warning: Could not initialize embedding model: {e}")
            self.embedding_model = None

    def save_query(
        self, 
        query_text: str, 
        connection_id: int, 
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        meta_info: Dict[str, Any] = None
    ):
        """
        Save a user query with its embedding.
        
        Args:
            query_text: 查询文本
            connection_id: 数据库连接ID
            tenant_id: 租户ID (多租户隔离必需)
            user_id: 用户ID
            meta_info: 元信息
        """
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
            tenant_id=tenant_id,
            user_id=user_id,
            meta_info=meta_info
        )
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def find_similar_queries(
        self, 
        query_text: str, 
        tenant_id: Optional[int] = None,
        connection_id: Optional[int] = None,
        limit: int = 5, 
        threshold: float = 0.7
    ) -> List[QueryHistory]:
        """
        Find similar queries using cosine similarity.
        
        多租户安全: 只在指定租户的历史中搜索。
        
        Args:
            query_text: 要匹配的查询文本
            tenant_id: 租户ID (多租户隔离)
            connection_id: 可选的连接ID过滤
            limit: 返回结果数量限制
            threshold: 相似度阈值
        """
        if not self.embedding_model:
            return []

        try:
            target_embedding = self.embedding_model.embed_query(query_text)
            
            # 构建查询，按租户过滤
            query = self.db.query(QueryHistory).filter(
                QueryHistory.embedding.isnot(None)
            )
            
            # 多租户隔离: 只查询指定租户的数据
            if tenant_id is not None:
                query = query.filter(QueryHistory.tenant_id == tenant_id)
            
            # 可选: 按连接ID过滤
            if connection_id is not None:
                query = query.filter(QueryHistory.connection_id == connection_id)
            
            history_items = query.all()
            
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
