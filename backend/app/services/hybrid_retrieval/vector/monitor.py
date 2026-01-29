"""
向量服务监控类
"""

import time
import logging
from typing import Dict, Any, List

from .service import VectorService

logger = logging.getLogger(__name__)


class VectorServiceMonitor:
    """向量服务监控类"""

    def __init__(self, service: VectorService):
        self.service = service
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "cache_hits": 0,
            "cache_misses": 0
        }

    async def embed_with_monitoring(self, question: str) -> List[float]:
        """带监控的嵌入"""
        start_time = time.time()
        self.metrics["total_requests"] += 1

        # 检查缓存
        if self.service._cache is not None:
            cached_result = self.service._get_from_cache(question)
            if cached_result is not None:
                self.metrics["cache_hits"] += 1
                return cached_result
            else:
                self.metrics["cache_misses"] += 1

        try:
            result = await self.service.embed_question(question)
            self.metrics["successful_requests"] += 1
            return result

        except Exception as e:
            self.metrics["failed_requests"] += 1
            raise e

        finally:
            response_time = time.time() - start_time
            self.metrics["total_response_time"] += response_time

    def get_metrics(self) -> Dict[str, Any]:
        """获取监控指标"""
        avg_response_time = (
            self.metrics["total_response_time"] / max(self.metrics["total_requests"], 1)
        )

        success_rate = (
            self.metrics["successful_requests"] / max(self.metrics["total_requests"], 1)
        )

        cache_hit_rate = (
            self.metrics["cache_hits"] / max(
                self.metrics["cache_hits"] + self.metrics["cache_misses"], 1
            )
        )

        return {
            **self.metrics,
            "average_response_time_ms": round(avg_response_time * 1000, 2),
            "success_rate": round(success_rate, 4),
            "cache_hit_rate": round(cache_hit_rate, 4)
        }
