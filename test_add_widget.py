"""
快速添加测试Widget到Dashboard
"""
import requests
import json

# 配置
API_BASE = "http://localhost:8000/api"
DASHBOARD_ID = 11  # 从URL看出是Dashboard 11

# 创建一个测试Widget
widget_data = {
    "widget_type": "chart",
    "title": "销售数据测试",
    "connection_id": 15,  # 使用默认连接ID
    "query_config": {
        "generated_sql": "SELECT * FROM orders LIMIT 100",
        "user_query": "查询订单数据"
    },
    "chart_config": {
        "chart_type": "bar"
    },
    "position_config": {
        "x": 0,
        "y": 0,
        "w": 6,
        "h": 4
    },
    "refresh_interval": 0
}

# 模拟一些数据缓存
widget_data["data_cache"] = {
    "data": [
        {"date": "2024-01-01", "sales": 1000, "quantity": 50},
        {"date": "2024-01-02", "sales": 1200, "quantity": 60},
        {"date": "2024-01-03", "sales": 900, "quantity": 45},
        {"date": "2024-01-04", "sales": 1500, "quantity": 75},
        {"date": "2024-01-05", "sales": 1300, "quantity": 65},
    ]
}

print(f"正在添加测试Widget到Dashboard {DASHBOARD_ID}...")

response = requests.post(
    f"{API_BASE}/dashboards/{DASHBOARD_ID}/widgets",
    json=widget_data
)

if response.status_code in [200, 201]:
    print("✅ Widget添加成功！")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    print("\n现在可以点击'生成洞察'按钮测试了！")
else:
    print(f"❌ 添加失败: {response.status_code}")
    print(response.text)
