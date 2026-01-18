"""
Phase 2 设置验证脚本
验证所有必需的依赖和配置是否正确

运行方式:
    python verify_phase2_setup.py
"""
import sys
import os


def check_dependencies():
    """检查必需的Python包"""
    print("\n=== 检查Python依赖 ===")
    
    required_packages = [
        ("langgraph", "LangGraph核心库"),
        ("langgraph.checkpoint.postgres", "PostgreSQL Checkpointer"),
        ("psycopg2", "PostgreSQL驱动"),
        ("langchain_core", "LangChain核心库"),
    ]
    
    missing = []
    
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"✓ {description}: {package}")
        except ImportError:
            print(f"✗ {description}: {package} (缺失)")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  缺少 {len(missing)} 个依赖包")
        print("\n请运行以下命令安装:")
        print("  pip install -r requirements.txt")
        return False
    else:
        print("\n✓ 所有依赖已安装")
        return True


def check_environment():
    """检查环境变量配置"""
    print("\n=== 检查环境变量 ===")
    
    # 尝试加载.env文件
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    
    if not os.path.exists(env_file):
        print(f"⚠️  .env文件不存在: {env_file}")
        print("请从.env.example复制并配置")
        return False
    
    print(f"✓ .env文件存在: {env_file}")
    
    # 检查关键配置
    required_vars = [
        "CHECKPOINT_MODE",
        "CHECKPOINT_POSTGRES_URI",
    ]
    
    # 读取.env文件
    env_vars = {}
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value
    
    missing = []
    for var in required_vars:
        if var in env_vars:
            value = env_vars[var]
            # 隐藏密码
            if 'URI' in var and '@' in value:
                display_value = value.split('@')[0].split(':')[0] + ":****@" + value.split('@')[1]
            else:
                display_value = value
            print(f"✓ {var}: {display_value}")
        else:
            print(f"✗ {var}: 未配置")
            missing.append(var)
    
    if missing:
        print(f"\n⚠️  缺少 {len(missing)} 个环境变量")
        return False
    else:
        print("\n✓ 所有环境变量已配置")
        return True


def check_checkpointer():
    """检查Checkpointer是否可以创建"""
    print("\n=== 检查Checkpointer ===")
    
    try:
        from app.core.checkpointer import get_checkpointer, check_checkpointer_health
        
        checkpointer = get_checkpointer()
        
        if checkpointer is None:
            print("⚠️  Checkpointer未启用 (mode=none)")
            print("如果需要多轮对话功能，请在.env中设置:")
            print("  CHECKPOINT_MODE=postgres")
            return True  # 这不是错误，只是未启用
        
        print(f"✓ Checkpointer类型: {type(checkpointer).__name__}")
        
        # 检查健康状态
        health = check_checkpointer_health()
        
        if health:
            print("✓ Checkpointer健康检查通过")
            return True
        else:
            print("✗ Checkpointer健康检查失败")
            print("\n请检查:")
            print("  1. PostgreSQL服务是否已启动")
            print("     docker-compose -f docker-compose.checkpointer.yml up -d")
            print("  2. CHECKPOINT_POSTGRES_URI配置是否正确")
            print("  3. 数据库连接是否正常")
            return False
            
    except Exception as e:
        print(f"✗ Checkpointer检查失败: {str(e)}")
        print("\n可能的原因:")
        print("  1. PostgreSQL服务未启动")
        print("  2. 依赖包未安装")
        print("  3. 配置错误")
        return False


def check_graph():
    """检查Graph是否可以创建"""
    print("\n=== 检查Graph ===")
    
    try:
        from app.agents.chat_graph import IntelligentSQLGraph
        
        graph = IntelligentSQLGraph()
        print(f"✓ Graph创建成功: {type(graph).__name__}")
        print(f"✓ Supervisor: {type(graph.supervisor_agent).__name__}")
        print(f"✓ Worker Agents数量: {len(graph.worker_agents)}")
        
        return True
        
    except Exception as e:
        print(f"✗ Graph创建失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("Phase 2 设置验证")
    print("=" * 60)
    
    results = []
    
    # 检查依赖
    results.append(("依赖检查", check_dependencies()))
    
    # 检查环境变量
    results.append(("环境变量", check_environment()))
    
    # 检查Checkpointer
    results.append(("Checkpointer", check_checkpointer()))
    
    # 检查Graph
    results.append(("Graph", check_graph()))
    
    # 总结
    print("\n" + "=" * 60)
    print("验证结果总结")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ 所有检查通过！Phase 2 已准备就绪。")
        print("\n下一步:")
        print("  1. 运行测试: python test_phase2_api_integration.py")
        print("  2. 启动服务: python chat_server.py")
        return 0
    else:
        print("\n✗ 部分检查失败，请根据上述提示修复问题。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
