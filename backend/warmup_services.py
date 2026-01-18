#!/usr/bin/env python3
"""
预热服务脚本
在应用启动后运行此脚本，预先初始化检索服务，提升首次查询性能

使用方式:
    python warmup_services.py
    
    或指定连接ID:
    python warmup_services.py --connections 10 15 20
"""

import asyncio
import argparse
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.chat_graph import warmup_services


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='预热SQL检索服务')
    parser.add_argument(
        '--connections',
        type=int,
        nargs='*',
        help='需要预热的数据库连接ID列表（可选）'
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("🔥 SQL检索服务预热工具")
    print("=" * 60)
    
    if args.connections:
        print(f"\n预热连接: {args.connections}")
    else:
        print("\n预热默认服务（无特定连接ID）")
    
    print("\n开始预热...")
    print("-" * 60)
    
    try:
        await warmup_services(connection_ids=args.connections)
        
        print("-" * 60)
        print("\n✅ 预热完成！")
        print("\n预热效果:")
        print("  • Milvus向量数据库已连接")
        print("  • Neo4j图数据库已连接")
        print("  • 向量服务已初始化")
        print("  • 检索引擎已就绪")
        print("\n后续查询将获得更快的响应速度！")
        
    except Exception as e:
        print(f"\n❌ 预热失败: {str(e)}")
        print("\n可能的原因:")
        print("  • Milvus服务未启动")
        print("  • Neo4j服务未启动")
        print("  • 网络连接问题")
        print("\n解决方案:")
        print("  1. 检查Docker容器: docker ps")
        print("  2. 查看服务日志: docker logs <container_id>")
        print("  3. 重启服务: docker-compose restart")
        print("\n注意: 预热失败不影响系统使用，只是首次查询可能较慢")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
