"""
LangGraph Checkpointer 测试脚本

功能：
- 测试 Checkpointer 创建
- 测试数据库连接
- 测试健康检查
- 验证配置正确性
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.checkpointer import (
    get_checkpointer, 
    check_checkpointer_health,
    reset_checkpointer,
    _mask_password
)
from app.core.config import settings


def print_section(title: str):
    """打印分节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_configuration():
    """测试配置"""
    print_section("1. 配置检查")
    
    print(f"✓ CHECKPOINT_MODE: {settings.CHECKPOINT_MODE}")
    print(f"✓ CHECKPOINT_POSTGRES_URI: {_mask_password(settings.CHECKPOINT_POSTGRES_URI or 'Not Set')}")
    print(f"✓ MAX_MESSAGE_HISTORY: {settings.MAX_MESSAGE_HISTORY}")
    print(f"✓ ENABLE_MESSAGE_SUMMARY: {settings.ENABLE_MESSAGE_SUMMARY}")
    print(f"✓ SUMMARY_THRESHOLD: {settings.SUMMARY_THRESHOLD}")
    
    # 验证配置
    if settings.CHECKPOINT_MODE == "postgres":
        if not settings.CHECKPOINT_POSTGRES_URI:
            print("\n✗ 错误: CHECKPOINT_POSTGRES_URI 未配置")
            return False
        print("\n✓ 配置验证通过")
        return True
    elif settings.CHECKPOINT_MODE == "none":
        print("\n⚠ Checkpointer 已禁用")
        return True
    else:
        print(f"\n✗ 错误: 不支持的 CHECKPOINT_MODE: {settings.CHECKPOINT_MODE}")
        return False


def test_checkpointer_creation():
    """测试 Checkpointer 创建"""
    print_section("2. Checkpointer 创建测试")
    
    try:
        # 重置以确保重新创建
        reset_checkpointer()
        
        print("正在创建 Checkpointer...")
        checkpointer = get_checkpointer()
        
        if checkpointer is None:
            if settings.CHECKPOINT_MODE == "none":
                print("✓ Checkpointer 已禁用（符合预期）")
                return True
            else:
                print("✗ Checkpointer 创建失败（返回 None）")
                return False
        
        print(f"✓ Checkpointer 创建成功")
        print(f"  类型: {type(checkpointer).__name__}")
        
        # 测试单例模式
        checkpointer2 = get_checkpointer()
        if checkpointer is checkpointer2:
            print("✓ 单例模式验证通过")
        else:
            print("✗ 单例模式验证失败")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Checkpointer 创建失败: {str(e)}")
        print("\n请检查：")
        print("1. PostgreSQL 容器是否运行: docker ps | grep langgraph-checkpointer-db")
        print("2. 连接配置是否正确: cat .env | grep CHECKPOINT")
        print("3. 数据库是否可访问: docker exec -it langgraph-checkpointer-db psql -U langgraph -d langgraph_checkpoints -c 'SELECT 1;'")
        return False


def test_health_check():
    """测试健康检查"""
    print_section("3. 健康检查测试")
    
    try:
        print("正在执行健康检查...")
        is_healthy = check_checkpointer_health()
        
        if is_healthy:
            print("✓ 健康检查通过")
            print("  Checkpointer 工作正常")
            return True
        else:
            if settings.CHECKPOINT_MODE == "none":
                print("⚠ Checkpointer 未启用")
                return True
            else:
                print("✗ 健康检查失败")
                return False
                
    except Exception as e:
        print(f"✗ 健康检查异常: {str(e)}")
        return False


def test_database_connection():
    """测试数据库连接"""
    print_section("4. 数据库连接测试")
    
    if settings.CHECKPOINT_MODE == "none":
        print("⚠ Checkpointer 未启用，跳过数据库测试")
        return True
    
    try:
        import psycopg2
        from urllib.parse import urlparse
        
        # 解析连接字符串
        uri = settings.CHECKPOINT_POSTGRES_URI
        if not uri:
            print("✗ 连接字符串未配置")
            return False
        
        parsed = urlparse(uri)
        
        print(f"正在连接数据库...")
        print(f"  主机: {parsed.hostname}")
        print(f"  端口: {parsed.port}")
        print(f"  数据库: {parsed.path[1:]}")
        print(f"  用户: {parsed.username}")
        
        # 尝试连接
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password
        )
        
        # 执行测试查询
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"\n✓ 数据库连接成功")
        print(f"  版本: {version.split(',')[0]}")
        
        # 检查表是否存在
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('checkpoints', 'checkpoint_writes')
        """)
        tables = cursor.fetchall()
        
        if tables:
            print(f"✓ 检查点表已创建:")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("⚠ 检查点表尚未创建（首次运行应用时会自动创建）")
        
        cursor.close()
        conn.close()
        
        return True
        
    except ImportError:
        print("⚠ psycopg2 未安装，跳过直接数据库测试")
        print("  可以安装: pip install psycopg2-binary")
        return True
        
    except Exception as e:
        print(f"✗ 数据库连接失败: {str(e)}")
        print("\n请检查：")
        print("1. PostgreSQL 容器是否运行")
        print("2. 端口映射是否正确")
        print("3. 用户名密码是否正确")
        return False


def print_summary(results: dict):
    """打印测试摘要"""
    print_section("测试摘要")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    print(f"\n总计: {total} 项测试")
    print(f"通过: {passed} 项 ✓")
    print(f"失败: {failed} 项 ✗")
    
    print("\n详细结果:")
    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {test_name}: {status}")
    
    if failed == 0:
        print("\n" + "=" * 60)
        print("  🎉 所有测试通过！Checkpointer 已就绪")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("  ⚠️  部分测试失败，请检查配置")
        print("=" * 60)
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("  LangGraph Checkpointer 测试")
    print("=" * 60)
    
    results = {}
    
    # 运行测试
    results["配置检查"] = test_configuration()
    results["Checkpointer 创建"] = test_checkpointer_creation()
    results["健康检查"] = test_health_check()
    results["数据库连接"] = test_database_connection()
    
    # 打印摘要
    success = print_summary(results)
    
    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
