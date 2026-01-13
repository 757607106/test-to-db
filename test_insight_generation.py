"""
测试Dashboard洞察生成完整流程
"""
import requests
import json

API_BASE = "http://localhost:8000/api"
DASHBOARD_ID = 11

# 测试数据
insight_request = {
    "conditions": {
        "time_range": {
            "relative_range": "last_30_days"
        },
        "aggregation_level": "day"
    },
    "use_graph_relationships": True
}

print("=" * 60)
print("测试Dashboard洞察生成功能")
print("=" * 60)

print(f"\n1. 发送洞察生成请求到 Dashboard {DASHBOARD_ID}...")
print(f"请求数据: {json.dumps(insight_request, indent=2, ensure_ascii=False)}")

try:
    response = requests.post(
        f"{API_BASE}/dashboards/{DASHBOARD_ID}/insights",
        json=insight_request,
        timeout=30
    )
    
    print(f"\n2. 响应状态码: {response.status_code}")
    
    if response.status_code == 200:
        print("\n✅ 洞察生成成功！")
        result = response.json()
        
        print(f"\n生成的洞察Widget ID: {result.get('widget_id')}")
        print(f"分析的Widget数量: {result.get('analyzed_widget_count')}")
        print(f"发现的表关系数量: {result.get('relationship_count')}")
        print(f"分析时间: {result.get('analysis_timestamp')}")
        
        insights = result.get('insights', {})
        
        print("\n--- 数据摘要 ---")
        summary = insights.get('summary', {})
        print(f"总数据行: {summary.get('total_rows')}")
        print(f"关键指标: {summary.get('key_metrics')}")
        
        if insights.get('trends'):
            print("\n--- 趋势分析 ---")
            trends = insights['trends']
            print(f"趋势方向: {trends.get('trend_direction')}")
            print(f"增长率: {trends.get('total_growth_rate')}%")
            print(f"描述: {trends.get('description')}")
        
        if insights.get('recommendations'):
            print("\n--- 业务建议 ---")
            for i, rec in enumerate(insights['recommendations'][:3], 1):
                print(f"{i}. [{rec.get('priority')}] {rec.get('content')}")
        
        print("\n\n🎉 测试成功！现在刷新浏览器页面查看洞察结果！")
        
    else:
        print(f"\n❌ 请求失败")
        print(f"错误信息: {response.text}")
        
except requests.exceptions.Timeout:
    print("\n⏱️ 请求超时（LLM调用可能较慢，这是正常的）")
    print("请稍后刷新页面查看结果")
except Exception as e:
    print(f"\n❌ 测试失败: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
