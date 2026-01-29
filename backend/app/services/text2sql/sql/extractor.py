"""
SQL 提取工具
从 LLM 响应中提取和清理 SQL 查询
"""

import re


def extract_sql_from_llm_response(response: str) -> str:
    """
    从LLM响应中提取SQL查询
    """
    # 查找SQL代码块
    sql_match = re.search(r'```sql\n(.*?)\n```', response, re.DOTALL)
    if sql_match:
        return sql_match.group(1).strip()

    # 查找任何代码块
    code_match = re.search(r'```(.*?)```', response, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()

    # 如果没有代码块，尝试找到类似SQL的内容
    lines = response.split('\n')
    sql_lines = []
    in_sql = False

    for line in lines:
        if line.strip().upper().startswith('SELECT'):
            in_sql = True

        if in_sql:
            sql_lines.append(line)

            if ';' in line:
                break

    if sql_lines:
        return '\n'.join(sql_lines)

    # 如果都失败了，返回整个响应
    return response


def clean_sql_from_llm_response(sql: str) -> str:
    """
    清理 LLM 响应中的 SQL (去除 markdown 包裹)
    
    Args:
        sql: 原始 SQL 字符串
        
    Returns:
        str: 清理后的 SQL
    """
    sql = sql.strip()
    
    # 去除 markdown 代码块
    if sql.startswith("```sql"):
        sql = sql[6:]
    elif sql.startswith("```"):
        sql = sql[3:]
    
    if sql.endswith("```"):
        sql = sql[:-3]
    
    return sql.strip()
