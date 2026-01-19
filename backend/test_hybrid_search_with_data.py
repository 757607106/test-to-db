#!/usr/bin/env python3
"""测试混合检索搜索功能 - 包含数据创建"""

import requests
import json

# API基础URL
BASE_URL = "http://localhost:8000/api"

def create_sample_qa_pairs(connection_id):
    """创建示例问答对"""
    
    sample_qa_pairs = [
        {
            "question": "查询所有产品的库存数量",
            "sql": "SELECT product_name, stock_quantity FROM products",
            "connection_id": connection_id,
            "query_type": "SELECT",
            "difficulty_level": 1,
            "verified": True
        },
        {
            "question": "统计库存数量大于50的产品数量",
            "sql": "SELECT COUNT(*) as count FROM products WHERE stock_quantity > 50",
            "connection_id": connection_id,
            "query_type": "AGGREGATE",
            "difficulty_level": 2,
            "verified": True
        },
        {
            "question": "查询库存最多的前5个产品",
            "sql": "SELECT product_name, stock_quantity FROM products ORDER BY stock_quantity DESC LIMIT 5",
            "connection_id": connection_id,
            "query_type": "ORDER_BY",
            "difficulty_level": 2,
            "verified": True
        },
        {
            "question": "按类别统计产品数量",
            "sql": "SELECT category, COUNT(*) as count FROM products GROUP BY category",
            "connection_id": connection_id,
            "query_type": "GROUP_BY",
            "difficulty_level": 3,
            "verified": True
        },
        {
            "question": "查询价格在100到500之间的产品信息",
            "sql": "SELECT * FROM products WHERE price BETWEEN 100 AND 500",
            "connection_id": connection_id,
            "query_type": "SELECT",
            "difficulty_level": 2,
            "verified": False
        }
    ]
    
    print(f"开始创建 {len(sample_qa_pairs)} 个示例问答对...")
    created_count = 0
    
    for i, qa_pair in enumerate(sample_qa_pairs, 1):
        try:
            response = requests.post(
                f"{BASE_URL}/hybrid-qa/qa-pairs/",
                json=qa_pair,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                created_count += 1
                print(f"  ✓ 创建成功 ({i}/{len(sample_qa_pairs)}): {qa_pair['question'][:50]}...")
            else:
                print(f"  ✗ 创建失败 ({i}/{len(sample_qa_pairs)}): {response.text[:100]}")
        except Exception as e:
            print(f"  ✗ 创建失败 ({i}/{len(sample_qa_pairs)}): {e}")
    
    print(f"成功创建 {created_count}/{len(sample_qa_pairs)} 个问答对\n")
    return created_count > 0


def test_search_functionality(connection_id):
    """测试搜索功能"""
    
    print("=" * 60)
    print("测试智能搜索功能")
    print("=" * 60)
    
    test_queries = [
        "查询产品库存",
        "统计产品信息",
        "产品数量",
        "库存最多的产品",
        "价格查询"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- 测试查询 {i} ---")
        print(f"问题: {query}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/hybrid-qa/qa-pairs/search",
                json={
                    "question": query,
                    "connection_id": connection_id,
                    "top_k": 3
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                results = response.json()
                print(f"找到 {len(results)} 个相似问答对:")
                
                for j, result in enumerate(results, 1):
                    print(f"\n  [{j}] 得分: {result['final_score']:.3f}")
                    print(f"      问题: {result['qa_pair']['question']}")
                    print(f"      SQL: {result['qa_pair']['sql'][:80]}...")
                    print(f"      推荐理由: {result['explanation']}")
            else:
                print(f"搜索失败: {response.text}")
                
        except Exception as e:
            print(f"搜索失败: {e}")


def main():
    print("混合检索智能搜索功能测试\n")
    
    # 1. 获取数据库连接
    print("=" * 60)
    print("步骤 1: 获取数据库连接")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/connections/")
        response.raise_for_status()
        connections = response.json()
        print(f"找到 {len(connections)} 个数据库连接:")
        for conn in connections:
            print(f"  - ID: {conn['id']}, Name: {conn['name']}, Type: {conn['db_type']}")
        
        if not connections:
            print("错误: 没有可用的数据库连接")
            return
        
        # 优先使用 inventory_demo (ID: 10)
        test_connection = None
        for conn in connections:
            if conn['name'] == 'inventory_demo' or conn['id'] == 10:
                test_connection = conn
                break
        
        if not test_connection:
            test_connection = connections[0]
        
        connection_id = test_connection['id']
        print(f"\n使用连接: {test_connection['name']} (ID: {connection_id})")
        
    except Exception as e:
        print(f"错误: 获取连接列表失败: {e}")
        return
    
    # 2. 检查现有问答对
    print("\n" + "=" * 60)
    print("步骤 2: 检查现有问答对")
    print("=" * 60)
    try:
        response = requests.get(
            f"{BASE_URL}/hybrid-qa/qa-pairs/",
            params={"connection_id": connection_id, "limit": 100}
        )
        response.raise_for_status()
        qa_pairs = response.json()
        print(f"现有问答对数量: {len(qa_pairs)}")
        
        if len(qa_pairs) == 0:
            print("没有问答对，需要创建示例数据...")
            # 3. 创建示例问答对
            print("\n" + "=" * 60)
            print("步骤 3: 创建示例问答对")
            print("=" * 60)
            if not create_sample_qa_pairs(connection_id):
                print("错误: 无法创建示例数据")
                return
        else:
            print("问答对已存在，跳过创建步骤")
            # 显示前几个
            for i, qa in enumerate(qa_pairs[:3], 1):
                print(f"  {i}. {qa['question'][:50]}...")
        
    except Exception as e:
        print(f"错误: 检查问答对失败: {e}")
        return
    
    # 4. 测试搜索功能
    print("\n" + "=" * 60)
    print("步骤 4: 测试智能搜索")
    print("=" * 60)
    test_search_functionality(connection_id)
    
    # 5. 显示统计信息
    print("\n" + "=" * 60)
    print("步骤 5: 统计信息")
    print("=" * 60)
    try:
        response = requests.get(
            f"{BASE_URL}/hybrid-qa/qa-pairs/stats",
            params={"connection_id": connection_id}
        )
        response.raise_for_status()
        stats = response.json()
        print(f"总问答对数: {stats.get('total_qa_pairs', 0)}")
        print(f"已验证数: {stats.get('verified_qa_pairs', 0)}")
        print(f"平均成功率: {stats.get('average_success_rate', 0):.2f}%")
        print(f"查询类型: {stats.get('query_types', {})}")
    except Exception as e:
        print(f"获取统计信息失败: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
