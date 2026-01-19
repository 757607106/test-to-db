#!/usr/bin/env python3
"""测试混合检索搜索功能"""

import requests
import json

# API基础URL
BASE_URL = "http://localhost:8000/api"

def test_search_qa_pairs():
    """测试搜索相似问答对"""
    
    # 1. 首先获取数据库连接列表
    print("=" * 50)
    print("1. 获取数据库连接列表")
    print("=" * 50)
    try:
        response = requests.get(f"{BASE_URL}/connections/")
        response.raise_for_status()
        connections = response.json()
        print(f"找到 {len(connections)} 个数据库连接:")
        for conn in connections:
            print(f"  - ID: {conn['id']}, Name: {conn['name']}, Type: {conn['db_type']}")
        
        if not connections:
            print("没有可用的数据库连接")
            return
        
        # 使用第一个连接进行测试
        test_connection_id = connections[0]['id']
        print(f"\n使用连接 ID: {test_connection_id} 进行测试")
    except Exception as e:
        print(f"获取连接列表失败: {e}")
        return
    
    # 2. 获取问答对列表
    print("\n" + "=" * 50)
    print("2. 获取问答对列表")
    print("=" * 50)
    try:
        response = requests.get(
            f"{BASE_URL}/hybrid-qa/qa-pairs/",
            params={"connection_id": test_connection_id, "limit": 10}
        )
        response.raise_for_status()
        qa_pairs = response.json()
        print(f"找到 {len(qa_pairs)} 个问答对:")
        for qa in qa_pairs[:5]:  # 只显示前5个
            print(f"  - ID: {qa['id']}")
            print(f"    问题: {qa['question'][:60]}...")
            print(f"    SQL: {qa['sql'][:60]}...")
        
        if not qa_pairs:
            print("没有可用的问答对，需要先创建一些问答对")
            return
        
        # 使用第一个问答对的问题进行搜索测试
        test_question = qa_pairs[0]['question']
    except Exception as e:
        print(f"获取问答对列表失败: {e}")
        test_question = "查询产品库存"  # 使用默认问题
    
    # 3. 测试智能搜索
    print("\n" + "=" * 50)
    print("3. 测试智能搜索功能")
    print("=" * 50)
    
    # 测试案例
    test_cases = [
        {
            "question": test_question,
            "connection_id": test_connection_id,
            "top_k": 5
        },
        {
            "question": "查询库存数量",
            "connection_id": test_connection_id,
            "top_k": 3
        },
        {
            "question": "统计产品信息",
            "top_k": 5  # 不指定connection_id，搜索所有
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- 测试案例 {i} ---")
        print(f"问题: {test_case['question']}")
        print(f"Connection ID: {test_case.get('connection_id', 'All')}")
        print(f"Top K: {test_case['top_k']}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/hybrid-qa/qa-pairs/search",
                json=test_case,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                results = response.json()
                print(f"找到 {len(results)} 个相似问答对:")
                
                for j, result in enumerate(results, 1):
                    print(f"\n  结果 {j}:")
                    print(f"    ID: {result['qa_pair']['id']}")
                    print(f"    问题: {result['qa_pair']['question'][:60]}...")
                    print(f"    SQL: {result['qa_pair']['sql'][:60]}...")
                    print(f"    最终得分: {result['final_score']:.4f}")
                    print(f"    语义得分: {result['semantic_score']:.4f}")
                    print(f"    结构得分: {result['structural_score']:.4f}")
                    print(f"    模式得分: {result['pattern_score']:.4f}")
                    print(f"    质量得分: {result['quality_score']:.4f}")
                    print(f"    推荐理由: {result['explanation'][:80]}...")
                
                if not results:
                    print("  未找到相似的问答对")
            else:
                print(f"请求失败: {response.text}")
                
        except requests.exceptions.Timeout:
            print("请求超时")
        except Exception as e:
            print(f"请求失败: {e}")
    
    # 4. 获取统计信息
    print("\n" + "=" * 50)
    print("4. 获取统计信息")
    print("=" * 50)
    try:
        response = requests.get(
            f"{BASE_URL}/hybrid-qa/qa-pairs/stats",
            params={"connection_id": test_connection_id}
        )
        response.raise_for_status()
        stats = response.json()
        print("统计信息:")
        print(f"  总问答对数: {stats.get('total_qa_pairs', 0)}")
        print(f"  已验证数: {stats.get('verified_qa_pairs', 0)}")
        print(f"  平均成功率: {stats.get('average_success_rate', 0):.2f}%")
        print(f"  查询类型分布: {stats.get('query_types', {})}")
        print(f"  难度分布: {stats.get('difficulty_distribution', {})}")
    except Exception as e:
        print(f"获取统计信息失败: {e}")


if __name__ == "__main__":
    print("开始测试混合检索搜索功能...\n")
    test_search_qa_pairs()
    print("\n测试完成!")
