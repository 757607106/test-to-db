from typing import Any
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
    """
    connection = crud.db_connection.get(db=db, id=chat_request.connection_id)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        # 生成或使用现有的对话ID
        conversation_id = chat_request.conversation_id or str(uuid4())
        
        # 构建查询文本（如果有澄清回复，需要整合）
        query_text = chat_request.natural_language_query
        if chat_request.clarification_responses:
            # 整合澄清信息
            clarification_context = "\n".join([
                f"问题: {resp.question_id}, 回答: {resp.answer}"
                for resp in chat_request.clarification_responses
            ])
            query_text = f"{query_text}\n\n澄清信息:\n{clarification_context}"
        
        # 创建 LangGraph 实例
        active_agent_profiles = []
        from app.crud.crud_agent_profile import agent_profile as crud_agent_profile
        
        if chat_request.agent_ids:
             for aid in chat_request.agent_ids:
                 profile = crud_agent_profile.get(db=db, id=aid)
                 if profile:
                     active_agent_profiles.append(profile)
        elif chat_request.agent_id:
            profile = crud_agent_profile.get(db=db, id=chat_request.agent_id)
            if profile:
                active_agent_profiles.append(profile)
        
        graph = IntelligentSQLGraph(active_agent_profiles=active_agent_profiles)
        
        # 处理查询
        from app.core.state import SQLMessageState
        from langchain_core.messages import HumanMessage
        
        # 初始化状态
        initial_state = SQLMessageState(
            messages=[HumanMessage(content=query_text)],
            connection_id=chat_request.connection_id,
            conversation_id=conversation_id,
            original_query=chat_request.natural_language_query,
            current_stage="clarification",
            retry_count=0,
            max_retries=3,
            max_clarification_rounds=2,
            error_history=[]
        )
        
        # 如果提供了澄清回复，更新澄清轮次
        if chat_request.clarification_responses:
            initial_state["clarification_round"] = len(chat_request.clarification_responses)
            initial_state["clarification_history"] = [
                {"question_id": r.question_id, "answer": r.answer}
                for r in chat_request.clarification_responses
            ]
        
        # 执行 graph (使用顶层图)
        final_state = await graph.graph.ainvoke(initial_state)
        
        # 检查路由结果
        route_decision = final_state.get("route_decision")
        if route_decision == "general_chat":
            messages = final_state.get("messages", [])
            last_msg = messages[-1] if messages else None
            response_text = last_msg.content if last_msg else ""
            return schemas.ChatQueryResponse(
                conversation_id=conversation_id,
                stage="general_chat",
                message=response_text
            )

        # 检查错误 (兼容之前的逻辑)
        # 如果没有 generated_sql 且有 error_history，或者 current_stage 为 error
        if final_state.get("current_stage") == "error":
             # 尝试获取最后一个错误
             errors = final_state.get("error_history", [])
             error_msg = errors[-1].get("error") if errors else "处理失败"
             return schemas.ChatQueryResponse(
                conversation_id=conversation_id,
                error=error_msg,
                stage="error"
            )
        
        # 提取结果
        response = schemas.ChatQueryResponse(
            conversation_id=conversation_id,
            stage=final_state.get("current_stage", "completed")
        )
        
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
            if exec_result.get("success"):
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
            conversation_id=chat_request.conversation_id or str(uuid4()),
            error=f"处理查询时出错: {str(e)}",
            stage="error"
        )
