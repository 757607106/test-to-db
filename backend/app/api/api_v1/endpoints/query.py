from typing import Any, List, Optional
from uuid import uuid4
import time
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage

from app import crud, schemas
from app.api import deps
from app.agents.chat_graph import IntelligentSQLGraph
from app.core.state import SQLMessageState
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=schemas.QueryResponse, deprecated=True)
async def execute_query(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    query_request: schemas.QueryRequest,
) -> Any:
    """
    Execute a natural language query against a database.
    
    ⚠️ DEPRECATED: 此接口已废弃，请使用 POST /query/chat 替代。
    
    此接口保留用于向后兼容，内部已重定向到新的 LangGraph 架构。
    """
    deps.get_verified_connection(db, query_request.connection_id, current_user)
    
    try:
        # ✅ 使用新的 LangGraph 架构替代旧的 text2sql_service
        graph = IntelligentSQLGraph()
        result = await graph.process_query(
            query=query_request.natural_language_query,
            connection_id=query_request.connection_id,
            tenant_id=current_user.tenant_id,
        )
        
        # 转换为旧格式响应
        if result.get("success"):
            final_state = result.get("result", {})
            return schemas.QueryResponse(
                sql=final_state.get("generated_sql", ""),
                results=_extract_results(final_state.get("execution_result")),
                error=None,
                context={"source": "langgraph_architecture"}
            )
        else:
            return schemas.QueryResponse(
                sql="",
                results=None,
                error=result.get("error", "Unknown error"),
                context=None
            )
    except Exception as e:
        return schemas.QueryResponse(
            sql="",
            results=None,
            error=f"Error processing query: {str(e)}",
            context=None
        )


def _extract_results(execution_result) -> Optional[Any]:
    """从执行结果中提取数据"""
    if execution_result is None:
        return None
    if hasattr(execution_result, 'data'):
        return execution_result.data
    if isinstance(execution_result, dict):
        return execution_result.get('data')
    return execution_result


@router.post("/chat", response_model=schemas.ChatQueryResponse)
async def chat_query(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    chat_request: schemas.ChatQueryRequest,
) -> Any:
    """
    支持多轮对话的智能查询接口
    包含澄清机制和分析洞察功能
    支持自定义数据分析智能体
    ✅ Phase 2: 支持thread_id实现真正的多轮对话和状态持久化
    """
    import logging
    logger = logging.getLogger(__name__)
    
    deps.get_verified_connection(db, chat_request.connection_id, current_user)
    
    try:
        # ✅ 使用conversation_id作为thread_id
        # 如果客户端提供了conversation_id，使用它作为thread_id
        # 否则生成新的UUID
        thread_id = chat_request.conversation_id or str(uuid4())
        
        logger.info(f"Processing chat query with thread_id: {thread_id}")
        
        # 构建查询文本（如果有澄清回复，需要整合）
        query_text = chat_request.natural_language_query
        if chat_request.clarification_responses:
            # 整合澄清信息
            clarification_context = "\n".join([
                f"问题: {resp.question_id}, 回答: {resp.answer}"
                for resp in chat_request.clarification_responses
            ])
            query_text = f"{query_text}\n\n澄清信息:\n{clarification_context}"
        
        # 处理自定义智能体
        custom_analyst = None
        if chat_request.agent_id:
            # 使用单个智能体（优先使用agent_id作为自定义分析专家）
            from app.crud.crud_agent_profile import agent_profile as crud_agent_profile
            from app.agents.agent_factory import create_custom_analyst_agent
            
            profile = crud_agent_profile.get(db=db, id=chat_request.agent_id)
            if profile:
                if not profile.is_system:
                    # 这是自定义智能体，用它替换默认的数据分析专家
                    logger.info(f"Using custom analyst agent: {profile.name} (id={profile.id})")
                    custom_analyst = create_custom_analyst_agent(profile, db)
                else:
                    logger.info(f"Agent {profile.name} is a system agent, using default workflow")
            else:
                logger.warning(f"Agent with id={chat_request.agent_id} not found, using default")
        
        # 创建 LangGraph 实例（传入自定义智能体）
        graph = IntelligentSQLGraph(custom_analyst=custom_analyst)
        
        # ✅ 使用新的process_query方法，传递thread_id
        # 这将启用状态持久化和多轮对话支持
        try:
            result = await graph.process_query(
                query=query_text,
                connection_id=chat_request.connection_id,
                thread_id=thread_id,  # ✅ 传递thread_id
                tenant_id=current_user.tenant_id,
            )
        except Exception as e:
            # 特殊处理 LangGraph 中断，虽然目前主要走 supervisor 的手动返回模式
            if "interrupt" in str(type(e).__name__).lower():
                logger.info(f"Graph interrupted for clarification: {thread_id}")
                # 尝试从状态中获取信息（如果需要）
                # 这里简单处理，因为 supervisor_agent 已经通过常规 return 处理了大部分澄清
                return schemas.ChatQueryResponse(
                    conversation_id=thread_id,
                    needs_clarification=True,
                    stage="clarification",
                    message="需要进一步澄清您的查询意图"
                )
            raise e
        
        # 构建响应
        response = schemas.ChatQueryResponse(
            conversation_id=thread_id,  # ✅ 返回thread_id作为conversation_id
            stage=result.get("final_stage", "completed")
        )
        
        # 检查成功/失败
        if not result.get("success"):
            response.error = result.get("error")
            return response
        
        # 提取结果
        final_state = result.get("result", {})
        
        # 检查路由结果
        route_decision = final_state.get("route_decision")
        if route_decision == "general_chat":
            messages = final_state.get("messages", [])
            last_msg = messages[-1] if messages else None
            response_text = last_msg.content if last_msg else ""
            response.message = response_text
            response.stage = "general_chat"
            return response

        # 检查错误 (兼容之前的逻辑)
        if final_state.get("current_stage") == "error":
             # 尝试获取最后一个错误
             errors = final_state.get("error_history", [])
             error_msg = errors[-1].get("error") if errors else "处理失败"
             response.error = error_msg
             response.stage = "error"
             return response
        
        # 检查是否需要澄清
        if final_state.get("needs_clarification") and final_state.get("clarification_questions"):
            response.needs_clarification = True
            response.clarification_questions = [
                schemas.ClarificationQuestion(**q)
                for q in final_state["clarification_questions"]
            ]
            return response
        
        # 提取 SQL 和结果
        if final_state.get("generated_sql"):
            response.sql = final_state["generated_sql"]
        
        if final_state.get("execution_result"):
            exec_result = final_state["execution_result"]
            # 兼容不同的结果格式
            if hasattr(exec_result, 'success') and exec_result.success:
                response.results = exec_result.data
            elif isinstance(exec_result, dict) and exec_result.get("success"):
                response.results = exec_result.get("data", [])
        
        # 提取分析洞察
        if final_state.get("analyst_insights"):
            insights = final_state["analyst_insights"]
            response.analyst_insights = schemas.AnalystInsights(**insights)
        
        # 提取图表配置
        if final_state.get("chart_config"):
            response.chart_config = final_state["chart_config"]
        
        return response
        
    except Exception:
        logger.exception("处理查询时出错")
        return schemas.ChatQueryResponse(
            conversation_id=thread_id if 'thread_id' in locals() else str(uuid4()),
            error="处理查询时出错",
            stage="error"
        )


@router.post("/chat/resume", response_model=schemas.ResumeQueryResponse)
async def resume_chat_query(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    resume_request: schemas.ResumeQueryRequest,
) -> Any:
    """
    恢复被interrupt暂停的查询 - LangGraph Command模式
    
    基于LangGraph官方示例: https://context7.com/langchain-ai/langgraph/llms.txt
    
    使用场景:
    - 用户回复澄清问题后，恢复执行
    - 需要用户确认某些操作时
    
    Args:
        resume_request:
            - thread_id: 会话线程ID
            - user_response: 用户的回复内容
            - connection_id: 数据库连接ID
    
    Returns:
        ResumeQueryResponse: 恢复执行后的结果
    """
    import logging
    from langgraph.types import Command
    
    logger = logging.getLogger(__name__)
    
    deps.get_verified_connection(db, resume_request.connection_id, current_user)
    
    try:
        logger.info(f"恢复查询执行: thread_id={resume_request.thread_id}")
        
        # 创建图实例
        graph = IntelligentSQLGraph()
        
        # ✅ LangGraph标准模式: 使用Command(resume=...)恢复执行
        # 参考: https://context7.com/langchain-ai/langgraph/llms.txt
        config = {"configurable": {"thread_id": resume_request.thread_id}}
        
        # Command(resume=user_response)告诉LangGraph:
        # 1. 从上次interrupt的地方继续
        # 2. 将user_response传递给interrupt()的返回值
        result = await graph.graph.ainvoke(
            Command(resume=resume_request.user_response),
            config=config
        )
        
        logger.info(f"查询恢复执行完成: thread_id={resume_request.thread_id}")
        
        # 解析结果
        response = schemas.ResumeQueryResponse(
            success=True,
            thread_id=resume_request.thread_id,
            stage=result.get("current_stage", "completed")
        )
        
        # 提取SQL和执行结果
        if result.get("generated_sql"):
            response.sql = result["generated_sql"]
        
        if result.get("execution_result"):
            exec_result = result["execution_result"]
            if hasattr(exec_result, 'success') and exec_result.success:
                response.results = exec_result.data
            elif isinstance(exec_result, dict) and exec_result.get("success"):
                response.results = exec_result.get("data", [])
        
        # 提取图表配置
        if result.get("chart_config"):
            response.chart_config = result["chart_config"]
        
        return response
        
    except Exception:
        logger.exception("恢复查询执行失败")
        return schemas.ResumeQueryResponse(
            success=False,
            thread_id=resume_request.thread_id,
            error="恢复执行失败",
            stage="error"
        )


@router.post("/chat/stream")
async def chat_query_stream(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    chat_request: schemas.ChatQueryRequest,
) -> StreamingResponse:
    """
    SSE流式聊天查询 - LangGraph标准astream模式
    
    基于LangGraph官方示例: https://github.com/langchain-ai/langgraph/examples
    
    特性:
    - 实时推送节点执行进度
    - Server-Sent Events (SSE)格式
    - 支持interrupt暂停和恢复
    
    前端使用EventSource接收:
    ```javascript
    const eventSource = new EventSource('/api/query/chat/stream');
    eventSource.addEventListener('node_update', (e) => {
        const data = JSON.parse(e.data);
        console.log(`节点: ${data.node}, 阶段: ${data.stage}`);
    });
    ```
    
    Args:
        chat_request: 聊天查询请求
    
    Returns:
        StreamingResponse: SSE流式响应
    """
    import logging
    logger = logging.getLogger(__name__)
    
    deps.get_verified_connection(db, chat_request.connection_id, current_user)
    
    async def event_generator():
        """SSE事件生成器"""
        try:
            thread_id = chat_request.conversation_id or str(uuid4())
            logger.info(f"开始流式执行: thread_id={thread_id}")
            
            # 创建图实例
            graph = IntelligentSQLGraph()
            
            # 构建初始状态
            initial_state = SQLMessageState(
                messages=[HumanMessage(content=chat_request.natural_language_query)],
                connection_id=chat_request.connection_id,
                thread_id=thread_id,
                tenant_id=current_user.tenant_id,
            )
            
            config = {"configurable": {"thread_id": thread_id}}
            
            # ✅ 使用astream流式执行 (LangGraph官方标准)
            # stream_mode="updates": 每个节点执行后推送增量更新
            async for chunk in graph.graph.astream(
                initial_state,
                config=config,
                stream_mode="updates"  # LangGraph官方推荐
            ):
                # chunk格式: {node_name: node_output}
                for node_name, node_output in chunk.items():
                    # 构建事件数据
                    event_data = {
                        "type": "node_update",
                        "node": node_name,
                        "stage": node_output.get("current_stage", "processing"),
                        "timestamp": time.time()
                    }
                    
                    # 添加节点特定数据
                    if node_name == "cache_check":
                        event_data["cache_hit"] = node_output.get("cache_hit", False)
                        if node_output.get("cache_hit_type"):
                            event_data["cache_hit_type"] = node_output["cache_hit_type"]
                    
                    elif node_name == "clarification":
                        if node_output.get("enriched_query"):
                            event_data["enriched_query"] = node_output["enriched_query"]
                    
                    elif node_name == "supervisor":
                        if node_output.get("generated_sql"):
                            event_data["sql"] = node_output["generated_sql"]
                        if node_output.get("execution_result"):
                            exec_result = node_output["execution_result"]
                            event_data["result_preview"] = {
                                "success": getattr(exec_result, 'success', False),
                                "row_count": len(getattr(exec_result, 'data', []) or [])
                            }
                    
                    # ✅ SSE格式推送事件
                    yield f"event: node_update\n"
                    yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            
            # 发送完成事件
            final_event = {
                "type": "complete",
                "thread_id": thread_id,
                "timestamp": time.time()
            }
            yield f"event: complete\n"
            yield f"data: {json.dumps(final_event, ensure_ascii=False)}\n\n"
            
            logger.info(f"流式执行完成: thread_id={thread_id}")
        
        except Exception as e:
            logger.exception("流式执行异常")
            # 发送错误事件
            error_event = {
                "type": "error",
                "error": "流式执行异常",
                "timestamp": time.time()
            }
            yield f"event: error\n"
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用nginx缓冲
        }
    )


@router.get("/conversations", response_model=List[schemas.ConversationSummary])
async def list_conversations(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    limit: int = 20,
    offset: int = 0
) -> Any:
    """
    查询会话列表
    
    ✅ Phase 2 新增API: 支持查询历史会话
    
    Args:
        limit: 返回的最大会话数（默认20）
        offset: 偏移量（用于分页）
        
    Returns:
        会话摘要列表
        
    说明:
        - 从Checkpointer中查询所有会话
        - 按更新时间倒序排列
        - 支持分页
    """
    import logging
    from app.core.checkpointer import get_checkpointer
    
    logger = logging.getLogger(__name__)
    
    try:
        checkpointer = get_checkpointer()
        
        if checkpointer is None:
            logger.warning("Checkpointer未启用，无法查询会话列表")
            return []
        
        # TODO: 实现会话查询逻辑
        # 不同的Checkpointer实现可能有不同的查询方法
        # PostgresSaver和SqliteSaver支持查询
        
        logger.info("会话列表查询功能待实现")
        return []
        
    except Exception as e:
        logger.error(f"查询会话列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询会话列表失败: {str(e)}")


@router.get("/conversations/{thread_id}", response_model=schemas.ConversationDetail)
async def get_conversation(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    thread_id: str
) -> Any:
    """
    获取会话详情
    
    ✅ Phase 2 新增API: 查询特定会话的完整历史
    
    Args:
        thread_id: 会话线程ID
        
    Returns:
        会话详情（包含完整的消息历史和状态）
        
    说明:
        - 从Checkpointer中查询指定会话的所有状态
        - 包含消息历史、状态快照、元数据等
    """
    import logging
    from app.core.checkpointer import get_checkpointer
    
    logger = logging.getLogger(__name__)
    
    try:
        checkpointer = get_checkpointer()
        
        if checkpointer is None:
            raise HTTPException(status_code=400, detail="Checkpointer未启用")
        
        # TODO: 实现会话详情查询
        # 使用checkpointer.list()方法查询特定thread_id的状态
        
        logger.info(f"会话详情查询功能待实现: thread_id={thread_id}")
        raise HTTPException(status_code=501, detail="功能待实现")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询会话详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询会话详情失败: {str(e)}")


@router.delete("/conversations/{thread_id}")
async def delete_conversation(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    thread_id: str
) -> Any:
    """
    删除会话
    
    ✅ Phase 2 新增API: 删除指定会话的所有状态
    
    Args:
        thread_id: 会话线程ID
        
    Returns:
        删除结果
        
    说明:
        - 从Checkpointer中删除指定会话的所有状态
        - 删除后无法恢复
        - 用于清理不需要的会话历史
    """
    import logging
    from app.core.checkpointer import get_checkpointer
    
    logger = logging.getLogger(__name__)
    
    try:
        checkpointer = get_checkpointer()
        
        if checkpointer is None:
            raise HTTPException(status_code=400, detail="Checkpointer未启用")
        
        # TODO: 实现会话删除
        # 不同的Checkpointer可能有不同的删除方法
        
        logger.info(f"会话删除功能待实现: thread_id={thread_id}")
        raise HTTPException(status_code=501, detail="功能待实现")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")
