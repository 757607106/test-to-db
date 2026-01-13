"""
更新Widget数据缓存
"""
import requests
import json

API_BASE = "http://localhost:8000/api"
WIDGET_ID = 1  # 刚创建的Widget ID

# 准备测试数据
data_cache = {
    "data": [
        {"date": "2024-01-01", "sales": 1000, "quantity": 50, "region": "华东"},
        {"date": "2024-01-02", "sales": 1200, "quantity": 60, "region": "华东"},
        {"date": "2024-01-03", "sales": 900, "quantity": 45, "region": "华北"},
        {"date": "2024-01-04", "sales": 1500, "quantity": 75, "region": "华东"},
        {"date": "2024-01-05", "sales": 1300, "quantity": 65, "region": "华北"},
        {"date": "2024-01-06", "sales": 1100, "quantity": 55, "region": "华南"},
        {"date": "2024-01-07", "sales": 1400, "quantity": 70, "region": "华东"},
        {"date": "2024-01-08", "sales": 1000, "quantity": 50, "region": "华北"},
        {"date": "2024-01-09", "sales": 1600, "quantity": 80, "region": "华东"},
        {"date": "2024-01-10", "sales": 1200, "quantity": 60, "region": "华南"},
    ],
    "columns": ["date", "sales", "quantity", "region"],
    "row_count": 10
}

print(f"正在更新Widget {WIDGET_ID}的数据...")

# 使用PATCH更新Widget
response = requests.patch(
    f"{API_BASE}/widgets/{WIDGET_ID}",
    json={"data_cache": data_cache}
)

if response.status_code == 200:
    print("✅ Widget数据更新成功！")
    print(f"数据行数: {data_cache['row_count']}")
    print("\n刷新页面后，再点击'生成洞察'按钮测试！")
else:
    print(f"❌ 更新失败: {response.status_code}")
    print(response.text)
