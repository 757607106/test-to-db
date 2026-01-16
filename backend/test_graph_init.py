"""测试chat graph初始化"""
from app.agents.chat_graph import create_intelligent_sql_graph

print("=" * 60)
print("测试Chat Graph初始化")
print("=" * 60)

try:
    print("\n创建IntelligentSQLGraph实例...")
    graph_instance = create_intelligent_sql_graph()
    
    print(f"✅ 图实例创建成功: {type(graph_instance).__name__}")
    print(f"✅ Supervisor代理: {type(graph_instance.supervisor_agent).__name__}")
    
    worker_agents = graph_instance.worker_agents
    print(f"✅ 工作代理数量: {len(worker_agents)}")
    
    print("\n工作代理列表:")
    for i, agent in enumerate(worker_agents):
        print(f"  {i+1}. {type(agent).__name__}")
    
    if len(worker_agents) == 5:
        print("\n✅ 工作代理数量正确 (5个)")
    else:
        print(f"\n❌ 工作代理数量不正确: 期望5个，实际{len(worker_agents)}个")
        exit(1)
    
    print("\n" + "=" * 60)
    print("✅ Chat Graph初始化测试通过")
    print("=" * 60)
    
except Exception as e:
    print(f"\n❌ Chat Graph初始化失败: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
