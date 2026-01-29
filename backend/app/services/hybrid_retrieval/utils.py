"""
混合检索服务 - 工具函数

包含:
- get_database_name_by_connection_id: 根据连接ID获取数据库名称
- extract_tables_from_sql: 从SQL中提取表名
- extract_entities_from_question: 从问题中提取实体
- clean_sql: 清理SQL语句
- generate_qa_id: 生成问答对ID
"""

import re
import uuid
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


def get_database_name_by_connection_id(connection_id: int) -> Optional[str]:
    """根据连接ID获取数据库名称"""
    try:
        from app.db.session import get_db
        from app.models.db_connection import DBConnection

        # 获取数据库会话
        db_gen = get_db()
        db = next(db_gen)

        try:
            # 查询数据库连接信息
            connection = db.query(DBConnection).filter(DBConnection.id == connection_id).first()
            if connection:
                return connection.database_name
            else:
                logger.warning(f"Connection with ID {connection_id} not found")
                return None
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to get database name for connection {connection_id}: {str(e)}")
        return None


def extract_tables_from_sql(sql: str) -> List[str]:
    """从SQL中提取表名"""
    # 移除注释和多余空格
    sql_clean = re.sub(r'--.*?\n', '', sql)
    sql_clean = re.sub(r'/\*.*?\*/', '', sql_clean, flags=re.DOTALL)
    sql_clean = ' '.join(sql_clean.split())

    # 查找FROM和JOIN后的表名
    pattern = r'(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    matches = re.findall(pattern, sql_clean, re.IGNORECASE)

    return list(set(matches))


def extract_entities_from_question(question: str) -> List[str]:
    """从问题中提取实体"""
    # 简单的实体提取逻辑，可以后续用NER模型替换
    entities = []

    # 常见的业务实体关键词
    entity_keywords = {
        '用户': ['用户', '客户', '会员', 'user', 'customer'],
        '订单': ['订单', '交易', 'order', 'transaction'],
        '产品': ['产品', '商品', '物品', 'product', 'item'],
        '部门': ['部门', '科室', 'department'],
        '员工': ['员工', '职员', 'employee', 'staff']
    }

    question_lower = question.lower()
    for entity, keywords in entity_keywords.items():
        if any(keyword in question_lower for keyword in keywords):
            entities.append(entity)

    return entities


def clean_sql(sql: str) -> str:
    """清理SQL语句"""
    # 移除代码块标记
    sql = re.sub(r'```sql\n?', '', sql)
    sql = re.sub(r'```\n?', '', sql)

    # 移除多余的空格和换行
    sql = ' '.join(sql.split())

    # 确保以分号结尾
    if not sql.strip().endswith(';'):
        sql = sql.strip() + ';'

    return sql


def generate_qa_id() -> str:
    """生成问答对ID"""
    return f"qa_{uuid.uuid4().hex[:12]}"
