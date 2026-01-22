"""
监督代理 (Supervisor Agent) - 使用 LangGraph 原生模式重构

遵循 LangGraph 官方最佳实践:
1. 移除 langgraph_supervisor 第三方库依赖
2. 使用原生条件边 (conditional_edges) 实现路由
3. 使用 LLM 进行智能路由决策
4. 简化消息管理，避免消息重复

官方文档参考:
- https://langchain-ai.github.io/langgraph/how-tos/react-agent-structured-output
- https://langchain-ai.github.io/langgraph/concepts/low_level
- https://dev.to/aiengineering/a-beginners-guide-to-handling-errors-in-langgraph-with-retry-policies-h22

核心职责:
1. 协调所有 Worker Agents 的工作流程
2. 根据任务阶段智能路由到合适的 Agent
3. 管理 Agent 间的消息传递和状态更新
4. 支持快速模式 (Fast Mode)
5. 智能错误恢复和重试决策

修复历史:
- 2026-01-22: 完善路由上下文，添加用户查询和错误详情
- 2026-01-22: 改进消息合并逻辑，避免重复消息
- 2026-01-23: 引入智能路由决策，改进错误恢复机制
- 2026-01-23: 添加死循环检测和错误模式识别
"""
from typing import Dict, Any, List, Optional, Literal
import logging
import json
import time

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

from app.core.state import SQLMessageState
from app.core.llms import get_default_model
from app.core.message_utils import validate_and_fix_message_history

logger = logging.getLogger(__name__)


# ============================================================================
# 路由决策 Schema (用于结构化输出)
# ============================================================================

class RouteDecision(BaseModel):
    """路由决策 - 用于 LLM 结构化输出"""
    next_agent: Literal[
        "schema_agent",
        "sql_generator_agent", 
        "sql_executor_agent",
        "chart_generator_agent",
        "error_recovery_agent",
        "FINISH"
    ] = Field(description="下一个要执行的 Agent 或 FINISH 表示完成")
    reason: str = Field(description="路由决策的简要原因")


# ============================================================================
# Supervisor 实现 (原生 LangGraph 模式)
# ============================================================================

class SupervisorAgent:
    """
    监督代理 - 使用 LangGraph 原生条件边模式
    
    重要变更 (2026-01-22):
    - 移除了 langgraph_supervisor 第三方库依赖
    - 使用原生条件边实现路由
    - 支持结构化输出进行路由决策
    
    架构模式:
    - 基于状态的路由：根据 current_stage 字段路由
    - LLM 辅助决策：复杂情况下使用 LLM 判断
    - 简化消息管理：避免消息重复
    """
    
    def __init__(self, worker_agents: List[Any] = None, custom_analyst=None):
        """
        初始化 Supervisor
        
        Args:
            worker_agents: 工作智能体列表（可选）
            custom_analyst: 自定义数据分析专家（可选）
        """
        self.llm = get_default_model()
        self.custom_analyst = custom_analyst
        self.worker_agents = worker_agents or self._create_worker_agents()
        
        # 尝试启用结构化输出
        try:
            self.router_llm = self.llm.with_structured_output(RouteDecision)
            logger.info("✓ Supervisor 路由器已启用结构化输出")
        except Exception as e:
            logger.warning(f"⚠ Supervisor 结构化输出不可用: {e}")
            self.router_llm = None
    
    # ✅ 性能优化: 类级别缓存默认 Worker Agents
    _cached_default_workers: List[Any] = None
    
    def _create_worker_agents(self) -> List[Any]:
        """
        创建工作代理
        
        性能优化: 缓存默认 Worker Agents，避免重复导入和创建
        
        Agent 职责分离:
        - data_analyst_agent: 数据分析和洞察生成
        - chart_generator_agent: 图表配置生成
        """
        # 如果有自定义分析专家，用它替换默认的 data_analyst_agent
        if self.custom_analyst:
            from app.agents.agents.schema_agent import schema_agent
            from app.agents.agents.sql_generator_agent import sql_generator_agent
            from app.agents.agents.sql_executor_agent import sql_executor_agent
            from app.agents.agents.error_recovery_agent import error_recovery_agent
            from app.agents.agents.chart_generator_agent import chart_generator_agent
            
            logger.info("使用自定义分析专家替换默认数据分析智能体")
            return [
                schema_agent,
                sql_generator_agent,
                sql_executor_agent,
                error_recovery_agent,
                self.custom_analyst,  # 自定义分析专家
                chart_generator_agent  # 图表生成仍使用默认
            ]
        
        # ✅ 返回缓存的默认 Worker Agents
        if SupervisorAgent._cached_default_workers is None:
            from app.agents.agents.schema_agent import schema_agent
            from app.agents.agents.sql_generator_agent import sql_generator_agent
            from app.agents.agents.sql_executor_agent import sql_executor_agent
            from app.agents.agents.error_recovery_agent import error_recovery_agent
            from app.agents.agents.data_analyst_agent import data_analyst_agent
            from app.agents.agents.chart_generator_agent import chart_generator_agent
            
            SupervisorAgent._cached_default_workers = [
                schema_agent,
                sql_generator_agent,
                sql_executor_agent,
                error_recovery_agent,
                data_analyst_agent,    # 数据分析专家
                chart_generator_agent  # 图表生成专家
            ]
            logger.info("✓ 默认 Worker Agents 已缓存（包含数据分析和图表生成智能体）")
        
        return SupervisorAgent._cached_default_workers
    
    def _get_agent_by_name(self, name: str):
        """根据名称获取 Agent"""
        for agent in self.worker_agents:
            if hasattr(agent, 'name') and agent.name == name:
                return agent
        return None
    
    def _extract_user_query(self, state: SQLMessageState) -> str:
        """从状态中提取用户原始查询"""
        # 优先使用已保存的原始查询
        if state.get("original_query"):
            return state["original_query"]
        
        # 使用增强后的查询
        if state.get("enriched_query"):
            return state["enriched_query"]
        
        # 从消息中提取
        messages = state.get("messages", [])
        for msg in messages:
            if hasattr(msg, 'type') and msg.type == 'human':
                content = msg.content
                if isinstance(content, list):
                    content = content[0].get("text", "") if content else ""
                return content
        return ""
    
    def _format_recent_errors(self, error_history: List[Dict[str, Any]], max_count: int = 3) -> str:
        """格式化最近的错误信息"""
        if not error_history:
            return "无错误记录"
        
        recent_errors = error_history[-max_count:]
        formatted = []
        
        for i, error in enumerate(recent_errors, 1):
            stage = error.get("stage", "unknown")
            error_msg = error.get("error", "")
            retry_count = error.get("retry_count", 0)
            timestamp = error.get("timestamp")
            
            error_info = f"{i}. [{stage}] {error_msg[:100]}"
            if retry_count > 0:
                error_info += f" (重试: {retry_count})"
            if timestamp:
                import datetime
                dt = datetime.datetime.fromtimestamp(timestamp)
                error_info += f" @ {dt.strftime('%H:%M:%S')}"
            
            formatted.append(error_info)
        
        return "\n".join(formatted)
    
    def _get_message_ids(self, messages: List) -> set:
        """获取消息ID集合，用于去重"""
        ids = set()
        for msg in messages:
            # 使用消息内容的哈希作为ID
            if hasattr(msg, 'content'):
                content = msg.content
                if isinstance(content, str):
                    ids.add(hash(content[:100]))  # 使用前100字符的哈希
                elif isinstance(content, list):
                    ids.add(hash(str(content)[:100]))
            # 对于 ToolMessage，还要检查 tool_call_id
            if isinstance(msg, ToolMessage):
                ids.add(msg.tool_call_id)
        return ids
    
    def route_by_stage(self, state: SQLMessageState) -> str:
        """
        基于状态的简单路由 (无需 LLM)
        
        这是推荐的路由方式：
        - 快速，无 LLM 调用
        - 基于 current_stage 字段
        - 明确的状态机转换
        
        流程:
        schema_analysis → sql_generation → sql_execution → analysis → chart_generation → completed
        
        职责分离:
        - data_analyst_agent: 数据分析和洞察生成
        - chart_generator_agent: 图表配置生成
        """
        current_stage = state.get("current_stage", "schema_analysis")
        fast_mode = state.get("fast_mode", False)
        skip_chart = state.get("skip_chart_generation", False)
        
        # 状态机路由
        if current_stage == "schema_analysis":
            return "schema_agent"
        
        elif current_stage == "sql_generation":
            return "sql_generator_agent"
        
        elif current_stage == "sql_execution":
            return "sql_executor_agent"
        
        # 新增：数据分析阶段（在 SQL 执行后）
        elif current_stage == "analysis":
            # 使用自定义分析专家或默认数据分析智能体
            if self.custom_analyst:
                return self.custom_analyst.name
            return "data_analyst_agent"
        
        elif current_stage == "chart_generation":
            if skip_chart:
                return "FINISH"
            return "chart_generator_agent"
        
        elif current_stage == "error_recovery":
            return "error_recovery_agent"
        
        elif current_stage == "completed":
            return "FINISH"
        
        else:
            logger.warning(f"未知的 stage: {current_stage}, 默认到 schema_analysis")
            return "schema_agent"
    
    async def route_with_llm(self, state: SQLMessageState) -> RouteDecision:
        """
        使用 LLM 进行智能路由 (复杂情况)
        
        仅在需要复杂决策时使用，提供完整的上下文信息
        
        修复 (2026-01-22): 添加用户查询和错误详情到上下文
        修复 (2026-01-23): 增强错误恢复决策能力，参考 LangChain 官方 Agent 设计
        
        参考: https://reference.langchain.com/python/langchain/agents/
        """
        if not self.router_llm:
            # 回退到简单路由
            next_agent = self.route_by_stage(state)
            return RouteDecision(next_agent=next_agent, reason="基于状态路由")
        
        # 提取完整的上下文信息
        user_query = self._extract_user_query(state)
        error_history = state.get("error_history", [])
        error_details = self._format_recent_errors(error_history)
        generated_sql = state.get("generated_sql", "")
        execution_result = state.get("execution_result")
        error_recovery_context = state.get("error_recovery_context")
        
        # 执行结果摘要
        exec_summary = "无"
        if execution_result:
            if hasattr(execution_result, 'success'):
                exec_summary = f"成功: {execution_result.success}"
                if execution_result.error:
                    exec_summary += f", 错误: {execution_result.error[:100]}"
                if execution_result.rows_affected:
                    exec_summary += f", 返回行数: {execution_result.rows_affected}"
            elif isinstance(execution_result, dict):
                exec_summary = f"成功: {execution_result.get('success', False)}"
                if execution_result.get('error'):
                    exec_summary += f", 错误: {execution_result.get('error', '')[:100]}"
        
        # 错误恢复上下文
        recovery_context = ""
        if error_recovery_context:
            recovery_context = f"""
=== 错误恢复上下文 ===
- 错误类型: {error_recovery_context.get('error_type', 'unknown')}
- 失败的SQL: {error_recovery_context.get('failed_sql', '')[:100]}...
- 建议动作: {error_recovery_context.get('recovery_action', 'unknown')}
- 已重试: {error_recovery_context.get('retry_count', 0)} 次
"""
        
        # 构建完整的路由上下文
        context = f"""
=== 用户查询 ===
{user_query[:200]}{'...' if len(user_query) > 200 else ''}

=== 当前状态 ===
- 阶段: {state.get('current_stage', 'unknown')}
- 快速模式: {state.get('fast_mode', False)}
- 跳过图表: {state.get('skip_chart_generation', False)}
- 重试次数: {state.get('retry_count', 0)} / {state.get('max_retries', 3)}
- 连接ID: {state.get('connection_id')}

=== 执行进度 ===
- Schema 信息: {'已获取' if state.get('schema_info') else '未获取'}
- 生成的 SQL: {generated_sql[:100] + '...' if generated_sql and len(generated_sql) > 100 else generated_sql or '无'}
- 执行结果: {exec_summary}
{recovery_context}
=== 错误历史 ({len(error_history)} 条) ===
{error_details}

=== 可用的 Agent ===
- schema_agent: 分析用户查询，获取数据库模式信息
- sql_generator_agent: 根据 schema 和查询生成 SQL 语句
- sql_executor_agent: 执行 SQL 查询并返回结果
- chart_generator_agent: 分析数据并生成可视化图表
- error_recovery_agent: 分析错误原因并制定恢复策略
- FINISH: 任务已完成，结束流程

请根据以上信息决定下一步应该调用哪个 Agent。
"""
        
        try:
            decision = await self.router_llm.ainvoke([
                SystemMessage(content="""你是一个智能路由器，负责决定 Text-to-SQL 流程的下一步。

## 核心决策原则

### 正常流程
1. 如果没有 schema 信息 → schema_agent
2. 有 schema 但没有 SQL → sql_generator_agent
3. 有 SQL 但没有执行结果 → sql_executor_agent
4. 执行成功且需要可视化 → chart_generator_agent
5. 一切完成 → FINISH

### 错误恢复决策 (重要!)
当出现错误时，你需要智能判断：

1. **SQL 语法/结构错误** (Unknown column, Unknown table, syntax error 等)
   - 如果重试次数 < 3 → sql_generator_agent (重新生成)
   - 已有 error_recovery_context → sql_generator_agent (带上下文重新生成)
   
2. **Schema 相关错误** (表不存在, 字段映射错误)
   - 可能需要重新获取 schema → schema_agent
   
3. **连接/权限错误**
   - 这类错误通常无法自动恢复 → FINISH (告知用户)
   
4. **达到重试上限**
   - retry_count >= max_retries → FINISH

### 关键判断
- 如果有 error_recovery_context 且 current_stage 是 sql_generation，说明正在重试，应该让 sql_generator_agent 继续
- 不要在可以重试时过早返回 FINISH
- 优先尝试自动修复，除非明确无法修复

### 输出格式
返回 next_agent 和决策原因。"""),
                HumanMessage(content=context)
            ])
            return decision
        except Exception as e:
            logger.error(f"LLM 路由失败: {e}")
            next_agent = self.route_by_stage(state)
            return RouteDecision(next_agent=next_agent, reason=f"LLM 失败，回退到状态路由: {e}")
    
    async def execute_agent(self, agent_name: str, state: SQLMessageState) -> Dict[str, Any]:
        """
        执行指定的 Agent
        
        Args:
            agent_name: Agent 名称
            state: 当前状态
            
        Returns:
            Agent 执行结果 (状态更新)
            
        修复 (2026-01-22): 添加时间戳到错误记录
        """
        agent = self._get_agent_by_name(agent_name)
        if not agent:
            logger.error(f"找不到 Agent: {agent_name}")
            return {
                "current_stage": "error_recovery",
                "error_history": state.get("error_history", []) + [{
                    "stage": "supervisor",
                    "error": f"找不到 Agent: {agent_name}",
                    "retry_count": state.get("retry_count", 0),
                    "timestamp": time.time()
                }]
            }
        
        try:
            start_time = time.time()
            logger.info(f"执行 Agent: {agent_name}")
            
            # 调用 Agent 的处理方法
            if hasattr(agent, 'process'):
                result = await agent.process(state)
            elif hasattr(agent, 'execute'):
                result = await agent.execute(state)
            elif hasattr(agent, 'agent') and hasattr(agent.agent, 'ainvoke'):
                # 兼容 ReAct Agent
                result = await agent.agent.ainvoke(state)
            else:
                raise ValueError(f"Agent {agent_name} 没有可调用的方法")
            
            elapsed = time.time() - start_time
            logger.info(f"Agent {agent_name} 执行完成，耗时 {elapsed:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Agent {agent_name} 执行失败: {e}")
            return {
                "current_stage": "error_recovery",
                "error_history": state.get("error_history", []) + [{
                    "stage": agent_name,
                    "error": str(e),
                    "retry_count": state.get("retry_count", 0),
                    "timestamp": time.time()
                }]
            }
    
    async def supervise(
        self, 
        state: SQLMessageState,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        监督整个流程 - 主要入口方法
        
        Args:
            state: SQL 消息状态
            config: LangGraph 配置（可选）
            
        Returns:
            执行结果
            
        修复 (2026-01-22): 改进消息合并逻辑，添加去重机制
        修复 (2026-01-23): 引入智能路由决策，在关键点使用 LLM 判断
        
        参考: https://reference.langchain.com/python/langchain/agents/
        """
        # 消息历史修剪
        from app.core.message_history import auto_trim_messages, get_message_stats
        
        if "messages" in state and state["messages"]:
            before_stats = get_message_stats(state["messages"])
            state["messages"] = auto_trim_messages(state["messages"])
            after_stats = get_message_stats(state["messages"])
            
            if after_stats["total"] < before_stats["total"]:
                logger.info(f"消息已修剪: {before_stats['total']} -> {after_stats['total']}")
        
        # 验证消息历史
        if "messages" in state and state["messages"]:
            state["messages"] = validate_and_fix_message_history(state["messages"])
        
        # 检查快速模式
        fast_mode = state.get("fast_mode", False)
        if fast_mode:
            logger.info("=== 快速模式已启用 ===")
        
        try:
            # 执行循环
            max_iterations = 10
            iteration = 0
            current_state = dict(state)
            
            while iteration < max_iterations:
                iteration += 1
                
                # ✅ 智能路由决策 - 在关键情况下使用 LLM
                next_agent = await self._intelligent_route(current_state, iteration)
                
                if next_agent == "FINISH":
                    logger.info("任务完成")
                    break
                
                # 执行 Agent
                result = await self.execute_agent(next_agent, current_state)
                
                # 更新状态（改进的消息合并逻辑）
                if result:
                    for key, value in result.items():
                        if key == "messages" and value:
                            # ✅ 改进：使用去重的消息合并
                            current_messages = current_state.get("messages", [])
                            existing_ids = self._get_message_ids(current_messages)
                            
                            new_messages = []
                            for msg in value:
                                # 检查是否是重复消息
                                msg_id = None
                                if hasattr(msg, 'content'):
                                    content = msg.content
                                    if isinstance(content, str):
                                        msg_id = hash(content[:100])
                                    elif isinstance(content, list):
                                        msg_id = hash(str(content)[:100])
                                
                                # 对于 ToolMessage，使用 tool_call_id 去重
                                if isinstance(msg, ToolMessage):
                                    if msg.tool_call_id in existing_ids:
                                        logger.debug(f"跳过重复的 ToolMessage: {msg.tool_call_id}")
                                        continue
                                    existing_ids.add(msg.tool_call_id)
                                elif msg_id and msg_id in existing_ids:
                                    logger.debug(f"跳过重复的消息")
                                    continue
                                
                                if msg_id:
                                    existing_ids.add(msg_id)
                                new_messages.append(msg)
                            
                            if new_messages:
                                current_state["messages"] = current_messages + new_messages
                                logger.debug(f"添加了 {len(new_messages)} 条新消息")
                        elif key == "error_history" and value:
                            # 错误历史也需要添加时间戳
                            current_errors = current_state.get("error_history", [])
                            for error in value:
                                if isinstance(error, dict) and "timestamp" not in error:
                                    error["timestamp"] = time.time()
                            current_state["error_history"] = current_errors + value
                        else:
                            current_state[key] = value
                
                # 检查是否完成
                if current_state.get("current_stage") == "completed":
                    logger.info("任务完成 (stage=completed)")
                    break
                
                # 检查错误重试限制
                if current_state.get("retry_count", 0) >= current_state.get("max_retries", 3):
                    logger.warning("达到最大重试次数，终止")
                    break
            
            if iteration >= max_iterations:
                logger.warning(f"达到最大迭代次数: {max_iterations}")
            
            return {
                "success": True,
                "result": current_state
            }
            
        except Exception as e:
            logger.error(f"Supervisor 执行出错: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _intelligent_route(self, state: SQLMessageState, iteration: int) -> str:
        """
        智能路由决策 - 在关键情况下使用 LLM 进行判断
        
        决策逻辑:
        1. 正常流程：使用状态机路由（快速）
        2. 错误恢复后：使用 LLM 智能决策
        3. 多次重试后：使用 LLM 评估是否继续
        4. 复杂情况：使用 LLM 判断最佳路径
        5. 检测死循环：同一阶段重复执行
        
        参考 LangChain 官方 create_agent 的设计理念:
        - Agent 应该能够自主决策
        - 在遇到问题时能够自我纠正
        - 参考: https://reference.langchain.com/python/langchain/agents/
        - 参考: https://dev.to/aiengineering/a-beginners-guide-to-handling-errors-in-langgraph-with-retry-policies-h22
        
        Args:
            state: 当前状态
            iteration: 当前迭代次数
            
        Returns:
            str: 下一个要执行的 Agent 名称
        """
        current_stage = state.get("current_stage", "schema_analysis")
        retry_count = state.get("retry_count", 0)
        error_history = state.get("error_history", [])
        error_recovery_context = state.get("error_recovery_context")
        
        # ✅ 死循环检测：检查是否同一阶段重复出错
        if self._detect_loop_pattern(error_history, current_stage):
            logger.warning(f"[死循环检测] 检测到重复错误模式，阶段: {current_stage}")
            # 尝试跳过当前阶段或直接结束
            if current_stage == "schema_analysis":
                logger.error("Schema 分析持续失败，终止流程")
                return "FINISH"
            elif current_stage == "sql_generation":
                # 可能是查询太复杂，建议用户简化
                logger.warning("SQL 生成持续失败，终止流程")
                return "FINISH"
        
        # ✅ 关键修复：error_recovery 阶段必须先执行 error_recovery_agent
        # 只有 error_recovery_agent 会：
        # 1. 递增 retry_count
        # 2. 设置 error_recovery_context（包含失败的 SQL 和修复建议）
        # 3. 分析错误类型并决定下一步行动
        if current_stage == "error_recovery" and error_recovery_context is None:
            logger.info(f"[智能决策] 迭代={iteration}, 阶段=error_recovery, 强制执行 error_recovery_agent (retry={retry_count}, errors={len(error_history)})")
            return "error_recovery_agent"
        
        # ✅ 关键修复：正常流程阶段直接使用状态机路由，不触发 LLM 决策
        # 这样可以避免 LLM 看到旧的错误信息后做出错误判断
        # 只有当 error_recovery_context 存在时（说明是错误恢复后的重试），才需要 LLM 决策
        normal_flow_stages = ["schema_analysis", "sql_generation", "sql_execution", "analysis", "chart_generation", "completed"]
        if current_stage in normal_flow_stages and error_recovery_context is None:
            logger.info(f"[状态机路由] 迭代={iteration}, 阶段={current_stage}, 使用状态机路由")
            return self.route_by_stage(state)
        
        # 判断是否需要智能决策（仅用于错误恢复相关场景）
        needs_intelligent_decision = (
            # 1. 错误恢复后的重试决策（已有 error_recovery_context）
            error_recovery_context is not None or
            # 2. 迭代次数过多（可能陷入循环）
            iteration > 7
        )
        
        if needs_intelligent_decision and self.router_llm:
            logger.info(f"[智能决策] 迭代={iteration}, 阶段={current_stage}, 重试={retry_count}, 错误数={len(error_history)}, 有恢复上下文={error_recovery_context is not None}")
            
            try:
                # 使用 LLM 进行智能路由
                decision = await self.route_with_llm(state)
                logger.info(f"[智能决策] LLM 决定: {decision.next_agent}, 原因: {decision.reason}")
                return decision.next_agent
            except Exception as e:
                logger.warning(f"[智能决策] LLM 路由失败，回退到状态机: {e}")
                # 回退到状态机路由
                return self.route_by_stage(state)
        
        # 正常情况使用状态机路由（快速）
        return self.route_by_stage(state)
    
    def _detect_loop_pattern(self, error_history: List[Dict[str, Any]], current_stage: str) -> bool:
        """
        检测是否存在死循环模式
        
        如果同一阶段连续出错 2 次以上，且错误类型相同，认为是死循环
        
        Args:
            error_history: 错误历史记录
            current_stage: 当前阶段
            
        Returns:
            bool: 是否检测到死循环
        """
        if len(error_history) < 2:
            return False
        
        # 检查最近 3 个错误是否来自同一阶段
        recent_errors = error_history[-3:]
        same_stage_errors = [e for e in recent_errors if e.get("stage") == current_stage]
        
        if len(same_stage_errors) >= 2:
            # 检查错误消息是否相似
            error_messages = [e.get("error", "") for e in same_stage_errors]
            if len(set(error_messages)) == 1:
                # 完全相同的错误消息
                return True
            
            # 检查是否有相似的错误模式
            error_keywords = set()
            for msg in error_messages:
                msg_lower = msg.lower()
                if "unknown column" in msg_lower:
                    error_keywords.add("unknown_column")
                elif "syntax" in msg_lower:
                    error_keywords.add("syntax")
                elif "connection" in msg_lower:
                    error_keywords.add("connection")
            
            # 如果所有错误都是同一类型
            if len(error_keywords) == 1:
                return True
        
        return False


# ============================================================================
# 工厂函数 (带缓存优化)
# ============================================================================

# ✅ 性能优化: 缓存默认 Supervisor 实例
_default_supervisor: Optional[SupervisorAgent] = None


def create_supervisor_agent(worker_agents: List[Any] = None, custom_analyst=None) -> SupervisorAgent:
    """创建监督代理实例"""
    return SupervisorAgent(worker_agents, custom_analyst)


def create_intelligent_sql_supervisor(custom_analyst=None) -> SupervisorAgent:
    """
    创建智能 SQL 监督代理
    
    性能优化: 如果没有自定义分析专家，返回缓存的默认实例
    """
    global _default_supervisor
    
    # 如果有自定义分析专家，创建新实例
    if custom_analyst is not None:
        logger.info("创建带自定义分析专家的 Supervisor 实例")
        return SupervisorAgent(custom_analyst=custom_analyst)
    
    # 返回缓存的默认实例
    if _default_supervisor is None:
        logger.info("首次创建默认 Supervisor 实例（将被缓存）")
        _default_supervisor = SupervisorAgent()
    else:
        logger.debug("✓ 使用缓存的默认 Supervisor 实例")
    
    return _default_supervisor


# ============================================================================
# 节点函数 (用于 LangGraph 图)
# ============================================================================

async def supervisor_node(state: SQLMessageState) -> Dict[str, Any]:
    """
    Supervisor 节点函数 - 用于 LangGraph 图
    
    这个函数包装了 SupervisorAgent，可以直接在图中使用。
    """
    supervisor = SupervisorAgent()
    result = await supervisor.supervise(state)
    
    if result.get("success"):
        return result.get("result", state)
    else:
        return {
            "current_stage": "error_recovery",
            "error_history": state.get("error_history", []) + [{
                "stage": "supervisor",
                "error": result.get("error", "Unknown error")
            }]
        }


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "SupervisorAgent",
    "create_supervisor_agent",
    "create_intelligent_sql_supervisor",
    "supervisor_node",
    "RouteDecision",
]
