"""
TrueSupervisor - 真正的中心枢纽 Supervisor

遵循 LangGraph 官方 Supervisor 模式:
1. 接收每个 Agent 的结果
2. 决定下一步调用谁
3. 汇总最终响应

与当前架构的区别:
- 当前: supervisor_subgraph 只是流程中的一个子图，内部也是 Pipeline
- 新架构: Supervisor 是整个系统的中心，所有 Agent 都向它报告

核心职责:
1. 意图识别 (data_query / general_chat)
2. 缓存检查 (三级缓存)
3. 澄清检测 (模糊则 interrupt)
4. 动态路由决策 (基于状态决定调用哪个 Agent)
5. 错误恢复决策
6. 结果汇总与格式化
"""

from typing import Dict, Any, List, Optional, Literal
import logging
import time

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from pydantic import BaseModel, Field

from app.core.state import SQLMessageState
from app.core.llms import get_default_model

logger = logging.getLogger(__name__)


# ============================================================================
# 路由决策 Schema
# ============================================================================

class SupervisorDecision(BaseModel):
    """Supervisor 路由决策"""
    next_agent: Literal[
        "schema_agent",
        "sql_generator",
        "sql_executor", 
        "data_analyst",
        "chart_generator",
        "error_recovery",
        "general_chat",
        "FINISH"
    ] = Field(description="下一个要执行的 Agent")
    reason: str = Field(description="决策原因")
    should_aggregate: bool = Field(default=False, description="是否需要汇总结果")


# ============================================================================
# TrueSupervisor 实现
# ============================================================================

class TrueSupervisor:
    """
    真正的中心枢纽 Supervisor
    
    架构模式: Hub-and-Spoke
    - Supervisor 是唯一的中心节点
    - 所有 Worker Agent 执行完都返回 Supervisor
    - Supervisor 决定下一步并汇总结果
    """
    
    def __init__(self):
        self.llm = get_default_model()
        self._start_time = None
        
        # 尝试启用结构化输出
        try:
            self.router_llm = self.llm.with_structured_output(SupervisorDecision)
        except Exception as e:
            logger.warning(f"结构化输出不可用: {e}")
            self.router_llm = None
    
    # ========================================================================
    # 核心方法: 路由决策
    # ========================================================================
    
    async def route(self, state: SQLMessageState) -> str:
        """
        决定下一步调用哪个 Agent
        
        这是 Supervisor 的核心方法，基于当前状态动态决策
        而不是固定的 Pipeline 流程
        
        Returns:
            下一个要执行的 Agent 名称，或 "FINISH" 表示完成
        """
        self._start_time = self._start_time or time.time()
        
        current_stage = state.get("current_stage", "init")
        logger.info(f"[Supervisor] 当前阶段: {current_stage}")
        
        # 1. 检查是否闲聊
        if self._is_general_chat(state):
            logger.info("[Supervisor] 路由 → general_chat")
            return "general_chat"
        
        # 2. 检查缓存 (三级缓存)
        if current_stage == "init":
            cache_hit = await self._check_cache(state)
            if cache_hit:
                logger.info(f"[Supervisor] 缓存命中 ({cache_hit}), 路由 → FINISH")
                return "FINISH"
        
        # 3. 检查是否需要澄清
        if self._needs_clarification(state) and current_stage in ["init", "clarification_pending"]:
            logger.info("[Supervisor] 需要澄清, 触发 interrupt")
            return "clarification"
        
        # 4. 基于阶段的动态路由
        next_agent = self._route_by_stage(state)
        logger.info(f"[Supervisor] 路由 → {next_agent}")
        return next_agent
    
    def _route_by_stage(self, state: SQLMessageState) -> str:
        """基于当前阶段决定下一步"""
        current_stage = state.get("current_stage", "init")
        error_history = state.get("error_history", [])
        
        # 错误恢复逻辑
        if current_stage == "error_recovery":
            retry_count = state.get("retry_count", 0)
            max_retries = state.get("max_retries", 3)
            
            if retry_count >= max_retries:
                return "FINISH"
            
            # 分析错误类型决定重试哪个 Agent
            return self._decide_retry_agent(state)
        
        # 正常流程路由
        stage_routes = {
            "init": "schema_agent",
            "schema_done": "sql_generator",
            "sql_generated": "sql_executor",
            "execution_done": "data_analyst",
            "analysis_done": self._decide_chart_or_finish(state),
            "chart_done": "FINISH",
            "completed": "FINISH",
            
            # Agent 返回后的阶段
            "schema_analysis": "schema_agent",
            "sql_generation": "sql_generator", 
            "sql_execution": "sql_executor",
            "analysis": "data_analyst",
            "chart_generation": "chart_generator",
        }
        
        return stage_routes.get(current_stage, "FINISH")
    
    def _decide_chart_or_finish(self, state: SQLMessageState) -> str:
        """决定是否需要生成图表"""
        # 快速模式跳过图表
        if state.get("skip_chart_generation", False):
            return "FINISH"
        
        # 检查是否有可视化需求
        original_query = state.get("original_query", "")
        chart_keywords = ["图表", "图形", "可视化", "趋势", "分布", "对比", "chart", "graph"]
        
        if any(kw in original_query.lower() for kw in chart_keywords):
            return "chart_generator"
        
        # 检查数据是否适合可视化
        execution_result = state.get("execution_result")
        if execution_result and hasattr(execution_result, 'data'):
            data = execution_result.data
            if isinstance(data, list) and len(data) > 1:
                return "chart_generator"
        
        return "FINISH"
    
    def _decide_retry_agent(self, state: SQLMessageState) -> str:
        """决定错误恢复后重试哪个 Agent"""
        error_history = state.get("error_history", [])
        if not error_history:
            return "sql_generator"
        
        last_error = error_history[-1]
        error_stage = last_error.get("stage", "")
        error_msg = last_error.get("error", "").lower()
        
        # SQL 相关错误 → 重新生成 SQL
        if any(kw in error_msg for kw in ["column", "table", "syntax", "sql"]):
            return "sql_generator"
        
        # Schema 相关错误 → 重新获取 Schema
        if any(kw in error_msg for kw in ["schema", "not found", "doesn't exist"]):
            return "schema_agent"
        
        # 默认重试 SQL 生成
        return "sql_generator"
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    def _is_general_chat(self, state: SQLMessageState) -> bool:
        """检查是否是闲聊"""
        route_decision = state.get("route_decision")
        if route_decision == "general_chat":
            return True
        
        # 简单关键词检测
        messages = state.get("messages", [])
        if not messages:
            return False
        
        last_msg = messages[-1]
        content = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        
        chat_keywords = ["你好", "谢谢", "帮助", "你是谁", "hello", "hi", "thanks"]
        return any(kw in content.lower() for kw in chat_keywords)
    
    async def _check_cache(self, state: SQLMessageState) -> Optional[str]:
        """检查三级缓存"""
        # L0: Thread 历史
        if state.get("thread_history_hit"):
            return "thread_history"
        
        # L1/L2: 全局缓存
        if state.get("cache_hit"):
            return state.get("cache_hit_type", "exact")
        
        return None
    
    def _needs_clarification(self, state: SQLMessageState) -> bool:
        """检查是否需要澄清"""
        return state.get("needs_clarification", False)
    
    # ========================================================================
    # 结果汇总
    # ========================================================================
    
    async def aggregate(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        汇总所有 Agent 的执行结果
        
        这是 Hub-and-Spoke 架构的关键 - 统一汇总点
        
        Returns:
            final_response 字典，包含完整的响应结构
        """
        elapsed_time = time.time() - (self._start_time or time.time())
        
        # 提取执行结果
        execution_result = state.get("execution_result")
        data = None
        if execution_result:
            if hasattr(execution_result, 'data'):
                data = execution_result.data
            elif isinstance(execution_result, dict):
                data = execution_result.get("data")
        
        # 构造统一响应
        final_response = {
            "success": state.get("current_stage") not in ["error_recovery", "error"],
            "query": state.get("enriched_query") or state.get("original_query"),
            "sql": state.get("generated_sql"),
            "data": data,
            "analysis": state.get("analyst_insights"),
            "chart": state.get("chart_config"),
            "recommendations": state.get("recommended_questions", []),
            "source": self._determine_source(state),
            "metadata": {
                "execution_time": round(elapsed_time, 2),
                "connection_id": state.get("connection_id"),
                "cache_hit_type": state.get("cache_hit_type"),
                "fast_mode": state.get("fast_mode", False),
                "retry_count": state.get("retry_count", 0)
            }
        }
        
        # 错误信息
        if not final_response["success"]:
            error_history = state.get("error_history", [])
            if error_history:
                final_response["error"] = error_history[-1].get("error", "Unknown error")
        
        logger.info(f"[Supervisor] 结果汇总完成, 耗时: {elapsed_time:.2f}s")
        
        return {
            "final_response": final_response,
            "current_stage": "completed"
        }
    
    def _determine_source(self, state: SQLMessageState) -> str:
        """确定结果来源"""
        if state.get("thread_history_hit"):
            return "thread_history_cache"
        if state.get("cache_hit"):
            return f"{state.get('cache_hit_type', 'exact')}_cache"
        return "generated"
    
    # ========================================================================
    # 节点函数 (供 LangGraph 调用)
    # ========================================================================
    
    async def supervisor_node(self, state: SQLMessageState) -> Dict[str, Any]:
        """
        Supervisor 节点函数
        
        在 Hub-and-Spoke 架构中，这个函数在每个 Agent 执行后被调用
        负责决定下一步和汇总结果
        """
        current_stage = state.get("current_stage", "init")
        
        # 如果已完成，执行汇总
        if current_stage == "completed" or self._should_finish(state):
            return await self.aggregate(state)
        
        # 否则只记录状态，路由由条件边决定
        return {}
    
    def _should_finish(self, state: SQLMessageState) -> bool:
        """判断是否应该结束"""
        stage = state.get("current_stage", "")
        
        # 明确的结束阶段
        if stage in ["completed", "chart_done"]:
            return True
        
        # 分析完成且不需要图表
        if stage == "analysis_done" and state.get("skip_chart_generation", False):
            return True
        
        # 达到重试上限
        if state.get("retry_count", 0) >= state.get("max_retries", 3):
            return True
        
        return False


# ============================================================================
# 全局实例 (懒加载)
# ============================================================================

_supervisor_instance: TrueSupervisor = None


def get_supervisor() -> TrueSupervisor:
    """获取 Supervisor 单例"""
    global _supervisor_instance
    if _supervisor_instance is None:
        _supervisor_instance = TrueSupervisor()
    return _supervisor_instance
