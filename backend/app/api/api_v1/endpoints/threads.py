"""
Threads API - 分页查询 LangGraph threads
针对 langgraph dev 内存存储优化的分页方案
"""
from typing import Any, List, Optional
from datetime import datetime
import os
import httpx
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

LANGGRAPH_API_URL = os.getenv("LANGGRAPH_API_URL", "http://localhost:2024")

# 缓存 thread 列表（轻量级摘要）
_thread_cache: List[dict] = []
_cache_timestamp: float = 0
_cache_ttl: float = 30.0  # 缓存 30 秒


class ThreadSummary(BaseModel):
    thread_id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    status: Optional[str] = None
    first_message: Optional[str] = None
    metadata: Optional[dict] = None


class ThreadSearchRequest(BaseModel):
    metadata: Optional[dict] = None
    limit: int = 20
    offset: int = 0


class ThreadSearchResponse(BaseModel):
    threads: List[ThreadSummary]
    total: int
    limit: int
    offset: int
    has_more: bool


def extract_first_message(values: dict, max_length: int = 100) -> Optional[str]:
    """从 thread values 中提取第一条消息预览"""
    if not values or not isinstance(values, dict):
        return None
    
    messages = values.get("messages", [])
    if not messages or not isinstance(messages, list):
        return None
    
    first_msg = messages[0]
    if isinstance(first_msg, dict):
        content = first_msg.get("content", "")
        if isinstance(content, str):
            return content[:max_length] + ("..." if len(content) > max_length else "")
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    return text[:max_length] + ("..." if len(text) > max_length else "")
    return None


async def fetch_thread_summaries(metadata_filter: Optional[dict] = None) -> List[dict]:
    """
    分批获取 thread 摘要，避免一次性加载全部数据
    使用小批量请求 + 提取摘要的方式减少内存占用
    """
    global _thread_cache, _cache_timestamp
    
    import time
    now = time.time()
    
    # 检查缓存是否有效
    if _thread_cache and (now - _cache_timestamp) < _cache_ttl:
        if metadata_filter:
            return [t for t in _thread_cache if _match_metadata(t.get("metadata", {}), metadata_filter)]
        return _thread_cache
    
    summaries = []
    batch_size = 20  # 每批获取 20 个
    seen_ids = set()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 分批获取，最多获取 200 个 threads
        for _ in range(10):  # 最多 10 批
            params = {"limit": batch_size}
            if metadata_filter:
                params["metadata"] = metadata_filter
            
            try:
                response = await client.post(
                    f"{LANGGRAPH_API_URL}/threads/search",
                    json=params,
                )
                
                if response.status_code != 200:
                    break
                
                threads = response.json()
                if not threads:
                    break
                
                new_count = 0
                for thread in threads:
                    tid = thread.get("thread_id")
                    if tid and tid not in seen_ids:
                        seen_ids.add(tid)
                        new_count += 1
                        summaries.append({
                            "thread_id": tid,
                            "created_at": thread.get("created_at"),
                            "updated_at": thread.get("updated_at"),
                            "status": thread.get("status"),
                            "first_message": extract_first_message(thread.get("values", {})),
                            "metadata": thread.get("metadata"),
                        })
                
                # 如果返回的数量小于请求的，说明没有更多数据
                if len(threads) < batch_size or new_count == 0:
                    break
                    
            except Exception:
                break
    
    # 按 created_at 倒序排列
    summaries.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    
    # 更新缓存
    if not metadata_filter:
        _thread_cache = summaries
        _cache_timestamp = now
    
    return summaries


def _match_metadata(thread_meta: dict, filter_meta: dict) -> bool:
    """检查 thread 元数据是否匹配过滤条件"""
    for key, value in filter_meta.items():
        if thread_meta.get(key) != value:
            return False
    return True


@router.post("/search", response_model=ThreadSearchResponse)
async def search_threads(request: ThreadSearchRequest) -> Any:
    """
    搜索 threads 并返回分页结果
    使用缓存 + 分批获取策略优化性能
    """
    try:
        # 获取 thread 摘要列表（使用缓存）
        all_summaries = await fetch_thread_summaries(request.metadata)
        
        # 计算分页
        total = len(all_summaries)
        start = request.offset
        end = start + request.limit
        page_summaries = all_summaries[start:end]
        has_more = end < total
        
        threads = [ThreadSummary(**s) for s in page_summaries]
        
        return ThreadSearchResponse(
            threads=threads,
            total=total,
            limit=request.limit,
            offset=request.offset,
            has_more=has_more,
        )
        
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to LangGraph API: {str(e)}"
        )


@router.delete("/{thread_id}")
async def delete_thread(thread_id: str) -> Any:
    """删除指定的 thread"""
    global _thread_cache, _cache_timestamp
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{LANGGRAPH_API_URL}/threads/{thread_id}",
            )
            
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="Thread not found")
            
            if response.status_code not in (200, 204):
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"LangGraph API error: {response.text}"
                )
            
            # 清除缓存
            _thread_cache = [t for t in _thread_cache if t.get("thread_id") != thread_id]
            
            return {"message": "Thread deleted successfully"}
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to LangGraph API: {str(e)}"
        )


@router.post("/cache/clear")
async def clear_cache() -> Any:
    """清除 thread 缓存"""
    global _thread_cache, _cache_timestamp
    _thread_cache = []
    _cache_timestamp = 0
    return {"message": "Cache cleared"}
