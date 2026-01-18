from typing import Any, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session


from app import crud, schemas
from app.api import deps
from app.services.text2sql_service import process_text2sql_query
from app.agents.chat_graph import IntelligentSQLGraph

router = APIRouter()

@router.post("/", response_model=schemas.QueryResponse)
def execute_query(
    *,
    db: Session = Depends(deps.get_db),
    query_request: schemas.QueryRequest,
) -> Any:
    """
    Execute a natural language query against a database.
    """
    connection = crud.db_connection.get(db=db, id=query_request.connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        # Process the query
        result = process_text2sql_query(
            db=db,
            connection=connection,
            natural_language_query=query_request.natural_language_query
        )
        return result
    except Exception as e:
        return schemas.QueryResponse(
            sql="",
            results=None,
            error=f"Error processing query: {str(e)}",
            context=None
        )


@router.post("/chat", response_model=schemas.ChatQueryResponse)
async def chat_query(
    *,
    db: Session = Depends(deps.get_db),
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
    
    connection = crud.db_connection.get(db=db, id=chat_request.connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
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
        result = await graph.process_query(
            query=query_text,
            connection_id=chat_request.connection_id,
            thread_id=thread_id  # ✅ 传递thread_id
        )
        
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
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return schemas.ChatQueryResponse(
            conversation_id=thread_id if 'thread_id' in locals() else str(uuid4()),
            error=f"处理查询时出错: {str(e)}",
            stage="error"
        )


@router.get("/conversations", response_model=List[schemas.ConversationSummary])
async def list_conversations(
    *,
    db: Session = Depends(deps.get_db),
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
