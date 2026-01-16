"""
测试工具名称显示
检查所有 agent 的工具名称是否正确
"""
from app.agents.agents.schema_agent import schema_agent
from app.agents.agents.sample_retrieval_agent import sample_retrieval_agent
from app.agents.agents.sql_generator_agent import sql_generator_agent
from app.agents.agents.sql_executor_agent import sql_executor_agent


def test_tool_names():
    """测试所有 agent 的工具名称"""
    
    agents = [
        ("schema_agent", schema_agent),
        ("sample_retrieval_agent", sample_retrieval_agent),
        ("sql_generator_agent", sql_generator_agent),
        ("sql_executor_agent", sql_executor_agent),
    ]
    
    print("=" * 60)
    print("工具名称检查")
    print("=" * 60)
    
    for agent_name, agent in agents:
        print(f"\n{agent_name}:")
        print(f"  Agent Name: {agent.name}")
        print(f"  Tools Count: {len(agent.tools)}")
        
        for i, tool in enumerate(agent.tools, 1):
            # 获取工具名称
            tool_name = getattr(tool, 'name', 'UNKNOWN')
            tool_func_name = getattr(tool, 'func', None)
            if tool_func_name:
                tool_func_name = tool_func_name.__name__
            
            print(f"    {i}. {tool_name}")
            if tool_func_name and tool_func_name != tool_name:
                print(f"       (function: {tool_func_name})")
    
    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)


if __name__ == "__main__":
    test_tool_names()
