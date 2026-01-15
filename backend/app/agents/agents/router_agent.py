from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from app.core.agent_config import get_agent_llm, CORE_AGENT_ROUTER

class RouteDecision(BaseModel):
    """Router decision model"""
    target: Literal["general_chat", "data_query"] = Field(
        description="The target workflow for the user query. 'general_chat' for casual conversation, greetings, or non-data questions. 'data_query' for questions related to database, data analysis, charts, or business metrics."
    )

def route_query(query: str) -> str:
    """
    Classify user query to determine the workflow.
    """
    # 使用特定的核心配置
    llm = get_agent_llm(CORE_AGENT_ROUTER)
    
    # Use structured output for classification
    structured_llm = llm.with_structured_output(RouteDecision)
    
    system_prompt = """You are an intelligent router for a data analysis system.
    Your job is to classify the user's input into one of two categories:
    
    1. 'general_chat': 
       - Casual conversation (e.g., "Hello", "How are you?")
       - Self-identification questions (e.g., "Who are you?")
       - General knowledge questions NOT related to the user's business data.
       
    2. 'data_query':
       - Questions about specific data (e.g., "Show me sales for last month")
       - Requests for charts or visualization.
       - Analysis requests.
       - Questions involving database schema or structure.
       
    Return only the decision.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{query}")
    ])
    
    chain = prompt | structured_llm
    
    try:
        decision = chain.invoke({"query": query})
        return decision.target
    except Exception as e:
        print(f"Routing error: {e}, defaulting to general_chat")
        return "general_chat"
