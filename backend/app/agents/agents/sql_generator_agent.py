"""
SQL生成代理 - 优化版 (LangGraph Node)
负责根据模式信息和用户查询生成高质量的SQL语句
优化：使用 Structured Output 替代 ReAct 模式，提升速度和稳定性
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda

from app.core.state import SQLMessageState
from app.core.agent_config import get_agent_llm, get_agent_profile, CORE_AGENT_SQL_GENERATOR

# 定义结构化输出模型
class SQLOutput(BaseModel):
    """SQL生成结果的结构化输出"""
    thought_process: str = Field(..., description="生成SQL的思考过程，包括对用户意图的理解、表选择理由等")
    sql: str = Field(..., description="生成的SQL查询语句")
    used_tables: List[str] = Field(default_factory=list, description="查询中使用的表名列表")
    assumptions: Optional[str] = Field(None, description="生成的假设（针对模糊查询）")

class SQLGeneratorAgent:
    """SQL生成代理 - 基于结构化输出"""

    def __init__(self):
        self.name = "sql_generator_agent"
        # 使用特定的核心配置，如果不存在则自动回退到默认
        self.llm = get_agent_llm(CORE_AGENT_SQL_GENERATOR)
        self.profile = get_agent_profile(CORE_AGENT_SQL_GENERATOR)
        
        # 绑定结构化输出
        self.structured_llm = self.llm.with_structured_output(SQLOutput)
        
        # 兼容性包装：为 SupervisorAgent 提供 .agent 属性
        # 使用 RunnableLambda 包装 process 方法，并赋予名字
        self.agent = RunnableLambda(self.process).with_config({"run_name": self.name})
        # 确保 agent 有 name 属性（SupervisorAgent 可能直接访问）
        self.agent.name = self.name

    async def process(self, state: SQLMessageState, config: RunnableConfig = None) -> Dict[str, Any]:
        """
        处理SQL生成任务
        直接根据 Schema 和 User Query 生成 SQL，跳过 ReAct 循环
        """
        try:
            # 1. 获取上下文信息
            user_query = self._get_user_query(state)
            schema_info = state.get("schema_info", {})
            sample_retrieval_result = state.get("sample_retrieval_result", {})
            connection_id = state.get("connection_id", 15)
            
            # 获取数据库类型 (尝试从 state 或 service 获取，默认 mysql)
            db_type = "mysql"
            try:
                from app.services.db_service import get_db_connection_by_id
                connection = get_db_connection_by_id(connection_id)
                if connection:
                    db_type = connection.db_type
            except Exception:
                pass

            # 2. 构建 Prompt
            system_prompt = self._build_system_prompt(db_type)
            user_prompt = self._build_user_prompt(
                user_query, 
                schema_info, 
                sample_retrieval_result, 
                db_type
            )

            # 3. 调用 LLM 生成
            print(f"🚀 SQL生成中 (DB: {db_type})...")
            result: SQLOutput = await self.structured_llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt)
                ]
            )

            print(f"✅ SQL生成成功: {result.sql[:50]}...")

            # 4. 更新状态
            return {
                "generated_sql": result.sql,
                "current_stage": "sql_execution", # 跳过验证，直接进入执行阶段（后续可加验证）
                "agent_messages": {
                    "sql_generator": {
                        "thought_process": result.thought_process,
                        "used_tables": result.used_tables,
                        "assumptions": result.assumptions,
                        "sql": result.sql
                    }
                },
                # 必须返回 messages 以满足 Supervisor 的契约
                "messages": [
                    AIMessage(
                        content=f"已生成 SQL：\n```sql\n{result.sql}\n```\n\n思考过程：{result.thought_process}",
                        name="sql_generator_agent"
                    )
                ]
            }

        except Exception as e:
            print(f"❌ SQL生成失败: {str(e)}")
            error_info = {
                "stage": "sql_generation",
                "error": str(e),
                "retry_count": state.get("retry_count", 0)
            }
            return {
                "error_history": [error_info], # Append logic handled by reducer if configured, else replacement
                "current_stage": "error_recovery",
                "messages": [AIMessage(content=f"SQL生成遇到错误: {str(e)}")]
            }

    def _get_user_query(self, state: SQLMessageState) -> str:
        """从状态中提取用户查询"""
        messages = state.get("messages", [])
        if not messages:
            return ""
        # 倒序查找最后一条 HumanMessage
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "user":
                return msg.get("content", "")
            elif hasattr(msg, "type") and msg.type == "human":
                return msg.content
        return ""

    def _build_system_prompt(self, db_type: str) -> str:
        """构建系统提示词"""
        syntax_guide = self._get_syntax_guide(db_type)
        
        # 优先使用 Profile 中的 System Prompt
        if self.profile and self.profile.system_prompt:
             return self.profile.system_prompt.replace("{db_type}", db_type).replace("{syntax_guide}", syntax_guide)

        return f"""你是一个精通 {db_type} 的高级数据工程师。
你的目标是将自然语言问题转换为**语法完美、性能高效**的 SQL 查询。

**核心原则**：
1. **准确性**：严格基于提供的 Schema，不虚构表或列。
2. **安全性**：只生成 SELECT 查询，严禁修改数据。
3. **鲁棒性**：处理模糊时间（"最近" -> 30天）、模糊排序（"最好" -> 降序）。
4. **简洁性**：只查询必要的列，除非用户要求详情，否则默认 LIMIT 20。

**数据库规范 ({db_type})**：
{syntax_guide}
"""

    def _get_syntax_guide(self, db_type: str) -> str:
        if db_type.lower() == "mysql":
            return """
- 日期处理: DATE_FORMAT(col, '%Y-%m'), DATE_SUB(NOW(), INTERVAL 7 DAY)
- 字符串: CONCAT(a, b)
- 限制: LIMIT n (而非 TOP/ROWNUM)
- 聚合: 避免在 GROUP BY 中使用别名
"""
        elif db_type.lower() == "postgresql":
            return """
- 日期: DATE_TRUNC('month', col), CURRENT_DATE - INTERVAL '7 days'
- 字符串: a || b
- 限制: LIMIT n
- 大小写: 标识符默认小写，如有大写需加双引号
"""
        return ""

    def _build_user_prompt(
        self, 
        query: str, 
        schema_info: Dict[str, Any], 
        sample_results: Dict[str, Any],
        db_type: str
    ) -> str:
        """构建用户提示词"""
        
        # 1. Schema 上下文 (尝试提取精简信息)
        schema_context = ""
        if schema_info:
            # 兼容不同的 schema_info 结构
            tables = schema_info.get("tables", []) or schema_info.get("schema_context", {}).get("tables", [])
            relationships = schema_info.get("relationships", []) or schema_info.get("schema_context", {}).get("relationships", [])
            
            schema_context = "【数据库 Schema】\n"
            if isinstance(tables, list):
                for t in tables:
                    name = t.get("name")
                    desc = t.get("description", "")
                    schema_context += f"- 表 `{name}`: {desc}\n"
                    # 列信息可能在 schema_info 的 columns 中，或者需要单独传递
                    # 这里假设 schema_info 已经包含了足够的信息，或者 Agent 之前已经检索过
            
            # 如果 schema_info 包含原始文本描述 (legacy)
            if "schema_context" in schema_info and isinstance(schema_info["schema_context"], str):
                 schema_context = f"【数据库 Schema】\n{schema_info['schema_context']}\n"

        # 2. 样本参考 (Few-Shot)
        sample_context = ""
        if sample_results and sample_results.get("qa_pairs"):
            sample_context = "【参考案例 (Few-Shot)】\n"
            for i, qa in enumerate(sample_results["qa_pairs"][:2]): # 取 Top 2
                sample_context += f"案例 {i+1}:\nQ: {qa.get('question')}\nSQL: {qa.get('sql')}\n\n"

        return f"""
【用户问题】
{query}

{schema_context}

{sample_context}

【任务要求】
请根据上述信息生成 {db_type} SQL。
如果用户意图模糊（如"销售情况"），请默认按时间或金额聚合。
请输出结构化 JSON 格式。
"""

# 创建全局实例
sql_generator_agent = SQLGeneratorAgent()
