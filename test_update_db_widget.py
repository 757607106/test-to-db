"""
直接更新数据库中的Widget data_cache
"""
import sys
sys.path.append('/Users/pusonglin/chat-to-db/backend')

from app.db.session import SessionLocal
from app import crud
import json

db = SessionLocal()

try:
    # 获取Widget
    widget = crud.crud_dashboard_widget.get(db, id=1)
    
    if not widget:
        print("❌ Widget不存在")
        sys.exit(1)
    
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
    
    # 更新data_cache
    widget.data_cache = data_cache
    db.commit()
    db.refresh(widget)
    
    print("✅ Widget数据更新成功！")
    print(f"Widget ID: {widget.id}")
    print(f"标题: {widget.title}")
    print(f"数据行数: {len(data_cache['data'])}")
    print("\n现在刷新页面，点击'应用'按钮生成洞察！")
    
finally:
    db.close()
