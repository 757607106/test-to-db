"""
SQL 验证服务

在 SQL 执行前进行完整验证，确保：
1. 语法正确
2. 安全（无危险操作）
3. 资源可控（有 LIMIT 限制）
4. 列名/表名存在
5. 数据库方言兼容性

使用方式：
    from app.services.sql_validator import sql_validator
    
    result = sql_validator.validate(
        sql="SELECT * FROM products",
        schema_context=schema_context,
        db_type="mysql"
    )
    
    if not result.is_valid:
        print(result.errors)
"""
import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from app.services.db_dialect import validate_dialect_compatibility, get_dialect

logger = logging.getLogger(__name__)


@dataclass
class SQLValidationResult:
    """SQL 验证结果"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    fixed_sql: Optional[str] = None  # 自动修复后的 SQL（如添加 LIMIT）
    
    def add_error(self, error: str):
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)


class SQLValidator:
    """
    SQL 验证器
    
    验证层级：
    1. 基础语法检查
    2. 安全检查（禁止危险操作）
    3. 资源限制检查
    4. Schema 一致性检查
    """
    
    # 支持的数据库类型
    SUPPORTED_DB_TYPES = ['mysql', 'postgresql', 'sqlite', 'sqlserver', 'oracle']
    
    # 禁止的危险关键字（只读模式）
    DANGEROUS_KEYWORDS = [
        'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 
        'INSERT', 'UPDATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE'
    ]
    
    # 默认 LIMIT 值
    DEFAULT_LIMIT = 1000
    MAX_LIMIT = 10000
    
    # JOIN 数量限制
    MAX_JOINS = 5
    
    # 子查询深度限制
    MAX_SUBQUERY_DEPTH = 3
    
    def validate(
        self,
        sql: str,
        schema_context: Optional[Dict[str, Any]] = None,
        db_type: str = "mysql",
        allow_write: bool = False
    ) -> SQLValidationResult:
        """
        验证 SQL 语句
        
        Args:
            sql: SQL 语句
            schema_context: Schema 上下文（包含表和列信息）
            db_type: 数据库类型
            allow_write: 是否允许写操作（默认只读）
            
        Returns:
            SQLValidationResult: 验证结果
        """
        result = SQLValidationResult(is_valid=True)
        
        if not sql or not sql.strip():
            result.add_error("SQL 语句为空")
            return result
        
        sql = sql.strip()
        
        # 1. 基础语法检查
        self._check_basic_syntax(sql, result)
        if not result.is_valid:
            return result
        
        # 2. 安全检查
        if not allow_write:
            self._check_security(sql, result)
            if not result.is_valid:
                return result
        
        # 3. 资源限制检查
        fixed_sql = self._check_resource_limits(sql, db_type, result)
        if fixed_sql:
            result.fixed_sql = fixed_sql
        
        # 4. 数据库方言兼容性检查
        self._check_dialect_compatibility(sql, db_type, result)
        
        # 5. Schema 一致性检查（如果提供了 schema_context）
        if schema_context:
            self._check_schema_consistency(sql, schema_context, result)
        
        return result
    
    def _check_basic_syntax(self, sql: str, result: SQLValidationResult):
        """基础语法检查"""
        sql_upper = sql.upper().strip()
        
        # 检查是否以 SELECT 开头（只读模式）
        if not sql_upper.startswith('SELECT') and not sql_upper.startswith('WITH'):
            result.add_error(f"只支持 SELECT 查询，当前语句以 '{sql_upper.split()[0] if sql_upper else '空'}' 开头")
            return
        
        # 检查括号匹配
        open_parens = sql.count('(')
        close_parens = sql.count(')')
        if open_parens != close_parens:
            result.add_error(f"括号不匹配：左括号 {open_parens} 个，右括号 {close_parens} 个")
            return
        
        # 检查引号匹配（简单检查）
        single_quotes = sql.count("'")
        if single_quotes % 2 != 0:
            result.add_error("单引号不匹配")
            return
        
        # 检查是否有 FROM 子句（SELECT 语句必须有）
        if sql_upper.startswith('SELECT') and ' FROM ' not in sql_upper:
            # 允许 SELECT 1, SELECT NOW() 等不需要 FROM 的情况
            if not re.search(r'SELECT\s+[\d\w\(\)]+\s*$', sql_upper):
                result.add_warning("SELECT 语句缺少 FROM 子句")
    
    def _check_security(self, sql: str, result: SQLValidationResult):
        """安全检查 - 禁止危险操作"""
        sql_upper = sql.upper()
        
        for keyword in self.DANGEROUS_KEYWORDS:
            # 使用单词边界匹配，避免误判（如 UPDATED_AT 列名）
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                result.add_error(f"安全限制：禁止使用 {keyword} 操作")
                return
        
        # 检查注释中是否有可疑内容（SQL 注入防护）
        if '--' in sql or '/*' in sql:
            # 允许正常注释，但记录警告
            result.add_warning("SQL 包含注释，请确保内容安全")
        
        # 检查是否有多语句（分号分隔）
        # 移除字符串中的分号后检查
        sql_no_strings = re.sub(r"'[^']*'", '', sql)
        if ';' in sql_no_strings.rstrip(';'):
            result.add_error("安全限制：禁止执行多条 SQL 语句")
    
    def _check_dialect_compatibility(
        self,
        sql: str,
        db_type: str,
        result: SQLValidationResult
    ):
        """
        数据库方言兼容性检查
        
        使用 db_dialect 模块验证 SQL 是否符合目标数据库的语法要求。
        """
        dialect_result = validate_dialect_compatibility(sql, db_type)
        
        # 将方言验证的错误和警告合并到结果中
        for error in dialect_result.get("errors", []):
            result.add_error(error)
        
        for warning in dialect_result.get("warnings", []):
            result.add_warning(warning)
    
    def _check_resource_limits(
        self, 
        sql: str, 
        db_type: str,
        result: SQLValidationResult
    ) -> Optional[str]:
        """
        资源限制检查
        
        Returns:
            修复后的 SQL（如果添加了 LIMIT），否则 None
        """
        sql_upper = sql.upper()
        fixed_sql = None
        
        # 检查 JOIN 数量
        join_count = len(re.findall(r'\bJOIN\b', sql_upper))
        if join_count > self.MAX_JOINS:
            result.add_warning(f"JOIN 数量较多（{join_count} 个），可能影响性能")
        
        # 检查子查询深度
        subquery_depth = self._count_subquery_depth(sql)
        if subquery_depth > self.MAX_SUBQUERY_DEPTH:
            result.add_warning(f"子查询嵌套较深（{subquery_depth} 层），可能影响性能")
        
        # 检查是否有 LIMIT（SELECT 语句）
        if sql_upper.startswith('SELECT') or sql_upper.startswith('WITH'):
            has_limit = bool(re.search(r'\bLIMIT\s+\d+', sql_upper))
            
            # SQL Server 使用 TOP
            has_top = bool(re.search(r'\bTOP\s+\d+', sql_upper))
            
            # Oracle 12c+ 使用 FETCH FIRST
            has_fetch = bool(re.search(r'\bFETCH\s+FIRST\s+\d+', sql_upper))
            
            if not has_limit and not has_top and not has_fetch:
                result.add_warning(f"查询没有 LIMIT 限制，已自动添加 LIMIT {self.DEFAULT_LIMIT}")
                
                # 自动添加 LIMIT
                fixed_sql = self._add_limit(sql, db_type)
        
        # 检查现有 LIMIT 是否过大
        limit_match = re.search(r'\bLIMIT\s+(\d+)', sql_upper)
        if limit_match:
            limit_value = int(limit_match.group(1))
            if limit_value > self.MAX_LIMIT:
                result.add_warning(f"LIMIT 值过大（{limit_value}），已调整为 {self.MAX_LIMIT}")
                fixed_sql = re.sub(
                    r'\bLIMIT\s+\d+',
                    f'LIMIT {self.MAX_LIMIT}',
                    sql,
                    flags=re.IGNORECASE
                )
        
        # 检查现有 TOP 是否过大 (SQL Server)
        top_match = re.search(r'\bTOP\s+(\d+)', sql_upper)
        if top_match:
            top_value = int(top_match.group(1))
            if top_value > self.MAX_LIMIT:
                result.add_warning(f"TOP 值过大（{top_value}），已调整为 {self.MAX_LIMIT}")
                fixed_sql = re.sub(
                    r'\bTOP\s+\d+',
                    f'TOP {self.MAX_LIMIT}',
                    sql,
                    flags=re.IGNORECASE
                )
        
        # 检查现有 FETCH FIRST 是否过大 (Oracle)
        fetch_match = re.search(r'\bFETCH\s+FIRST\s+(\d+)', sql_upper)
        if fetch_match:
            fetch_value = int(fetch_match.group(1))
            if fetch_value > self.MAX_LIMIT:
                result.add_warning(f"FETCH FIRST 值过大（{fetch_value}），已调整为 {self.MAX_LIMIT}")
                fixed_sql = re.sub(
                    r'\bFETCH\s+FIRST\s+\d+',
                    f'FETCH FIRST {self.MAX_LIMIT}',
                    sql,
                    flags=re.IGNORECASE
                )
        
        return fixed_sql
    
    def _count_subquery_depth(self, sql: str) -> int:
        """计算子查询嵌套深度"""
        max_depth = 0
        current_depth = 0
        in_string = False
        string_char = None
        
        for i, char in enumerate(sql):
            # 处理字符串
            if char in ("'", '"') and (i == 0 or sql[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                continue
            
            if in_string:
                continue
            
            # 检查 SELECT 关键字（子查询开始）
            if sql[i:i+6].upper() == 'SELECT':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            
            # 简化：用括号近似判断子查询结束
            # 实际上应该用更复杂的解析
        
        return max_depth
    
    def _add_limit(self, sql: str, db_type: str) -> str:
        """为 SQL 添加 LIMIT 子句"""
        sql = sql.rstrip().rstrip(';')
        
        db_type_lower = db_type.lower()
        
        if db_type_lower in ('mysql', 'postgresql', 'sqlite'):
            return f"{sql} LIMIT {self.DEFAULT_LIMIT}"
        elif db_type_lower == 'sqlserver':
            # SQL Server 需要在 SELECT 后添加 TOP
            return re.sub(
                r'\bSELECT\b',
                f'SELECT TOP {self.DEFAULT_LIMIT}',
                sql,
                count=1,
                flags=re.IGNORECASE
            )
        elif db_type_lower == 'oracle':
            # Oracle 12c+ 使用 FETCH FIRST
            return f"{sql} FETCH FIRST {self.DEFAULT_LIMIT} ROWS ONLY"
        else:
            # 默认使用 LIMIT
            return f"{sql} LIMIT {self.DEFAULT_LIMIT}"
    
    def _check_schema_consistency(
        self,
        sql: str,
        schema_context: Dict[str, Any],
        result: SQLValidationResult
    ):
        """
        检查 SQL 与 Schema 的一致性
        
        验证：
        1. 表名是否存在
        2. 列名是否存在
        3. JOIN 关系是否与已知关系一致（如果提供了 relationships / join_rules）
        """
        # 提取 schema 中的表名和列名
        valid_tables = set()
        valid_columns = {}  # table_name -> set of column_names
        all_columns = set()  # 所有列名（用于无表名前缀的情况）
        
        # 从 schema_context 提取表和列信息
        tables = schema_context.get('tables', [])
        columns = schema_context.get('columns', [])
        relationships = schema_context.get('relationships', []) or []
        join_rules = schema_context.get('join_rules', []) or []
        
        for table in tables:
            table_name = table.get('table_name', '') if isinstance(table, dict) else getattr(table, 'table_name', '')
            if table_name:
                valid_tables.add(table_name.lower())
                valid_columns[table_name.lower()] = set()
        
        for col in columns:
            if isinstance(col, dict):
                table_name = col.get('table_name', '').lower()
                col_name = col.get('column_name', '').lower()
            else:
                table_name = getattr(col, 'table_name', '').lower()
                col_name = getattr(col, 'column_name', '').lower()
            
            if table_name and col_name:
                if table_name in valid_columns:
                    valid_columns[table_name].add(col_name)
                all_columns.add(col_name)
        
        if not valid_tables:
            # 没有 schema 信息，跳过检查
            return
        
        # 提取 SQL 中的表名
        sql_tables = self._extract_table_names(sql)
        for table in sql_tables:
            table_lower = table.lower()
            if table_lower not in valid_tables:
                # 检查是否是别名
                if not self._is_table_alias(sql, table):
                    result.add_error(f"表 '{table}' 不存在。可用的表: {', '.join(sorted(valid_tables))}")
        
        # 提取 SQL 中的列名并验证
        sql_columns = self._extract_column_references(sql)
        for table_ref, col_name in sql_columns:
            col_lower = col_name.lower()
            
            if table_ref:
                # 有表名前缀
                table_lower = table_ref.lower()
                if table_lower in valid_columns:
                    if col_lower not in valid_columns[table_lower] and col_lower != '*':
                        available_cols = ', '.join(sorted(valid_columns[table_lower]))
                        result.add_error(f"列 '{table_ref}.{col_name}' 不存在。表 '{table_ref}' 的可用列: {available_cols}")
            else:
                # 无表名前缀，检查是否在任何表中存在
                if col_lower not in all_columns and col_lower != '*':
                    # 可能是别名或函数，只记录警告
                    if not self._is_sql_function_or_keyword(col_name):
                        result.add_warning(f"列 '{col_name}' 可能不存在，请检查")

        if relationships or join_rules:
            self._check_join_relationship_consistency(
                sql=sql,
                relationships=relationships,
                join_rules=join_rules,
                valid_tables=valid_tables,
                valid_columns=valid_columns,
                result=result,
            )
    
    def _extract_table_names(self, sql: str) -> List[str]:
        """从 SQL 中提取表名"""
        tables = []
        
        # 匹配 FROM table_name 和 JOIN table_name
        patterns = [
            r'\bFROM\s+`?(\w+)`?',
            r'\bJOIN\s+`?(\w+)`?',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.extend(matches)
        
        return list(set(tables))

    def _check_join_relationship_consistency(
        self,
        sql: str,
        relationships: List[Any],
        join_rules: List[Any],
        valid_tables: set,
        valid_columns: Dict[str, set],
        result: SQLValidationResult,
    ) -> None:
        sql_no_strings = re.sub(r"'[^']*'", '', sql)
        alias_map = self._extract_table_aliases(sql_no_strings)

        allowed_relationships = set()
        relationship_candidates_by_pair = {}

        for rel in relationships:
            if isinstance(rel, dict):
                st = rel.get("source_table", "")
                sc = rel.get("source_column", "")
                tt = rel.get("target_table", "")
                tc = rel.get("target_column", "")
            else:
                st = getattr(rel, "source_table", "")
                sc = getattr(rel, "source_column", "")
                tt = getattr(rel, "target_table", "")
                tc = getattr(rel, "target_column", "")

            st_n = self._normalize_table_name(st)
            tt_n = self._normalize_table_name(tt)
            sc_n = (sc or "").strip().lower()
            tc_n = (tc or "").strip().lower()
            if not st_n or not tt_n or not sc_n or not tc_n:
                continue

            allowed_relationships.add((st_n, sc_n, tt_n, tc_n))
            allowed_relationships.add((tt_n, tc_n, st_n, sc_n))
            pair_key = tuple(sorted([st_n, tt_n]))
            relationship_candidates_by_pair.setdefault(pair_key, set()).add((st_n, sc_n, tt_n, tc_n))
            relationship_candidates_by_pair.setdefault(pair_key, set()).add((tt_n, tc_n, st_n, sc_n))

        for rule in join_rules:
            join_clause = None
            if isinstance(rule, dict):
                join_clause = rule.get("join_clause")
            elif isinstance(rule, str):
                join_clause = rule

            if not join_clause:
                continue

            for t1, c1, t2, c2 in self._extract_join_equalities(join_clause):
                allowed_relationships.add((t1, c1, t2, c2))
                allowed_relationships.add((t2, c2, t1, c1))
                pair_key = tuple(sorted([t1, t2]))
                relationship_candidates_by_pair.setdefault(pair_key, set()).add((t1, c1, t2, c2))
                relationship_candidates_by_pair.setdefault(pair_key, set()).add((t2, c2, t1, c1))

        if not allowed_relationships:
            return

        on_clauses = self._extract_on_clauses(sql_no_strings)
        for on_clause in on_clauses:
            equalities = self._extract_join_equalities(on_clause)
            if not equalities:
                result.add_warning("JOIN ON 子句未识别到列等值条件，无法校验关联关系")
                continue

            checked_pairs = set()
            hit_pairs = set()
            for t1, c1, t2, c2 in equalities:
                t1_actual = self._resolve_table_ref(t1, alias_map)
                t2_actual = self._resolve_table_ref(t2, alias_map)

                if not t1_actual or not t2_actual:
                    continue

                if t1_actual == t2_actual:
                    continue

                if valid_tables and (t1_actual not in valid_tables or t2_actual not in valid_tables):
                    continue

                pair_key = tuple(sorted([t1_actual, t2_actual]))
                checked_pairs.add(pair_key)
                if (t1_actual, c1, t2_actual, c2) in allowed_relationships:
                    hit_pairs.add(pair_key)
                    continue

            for pair_key in checked_pairs:
                if pair_key in hit_pairs:
                    continue
                candidates = relationship_candidates_by_pair.get(pair_key, set())
                if candidates:
                    candidate_str = "; ".join(
                        sorted([f"{a}.{b} = {c}.{d}" for a, b, c, d in candidates])[:8]
                    )
                    result.add_error(f"JOIN 关系不一致：{pair_key[0]} 与 {pair_key[1]} 的关联必须匹配: {candidate_str}")
                else:
                    result.add_error(f"JOIN 关系不一致：{pair_key[0]} 与 {pair_key[1]} 的关联不在允许范围内")

    def _normalize_table_name(self, table_name: str) -> str:
        if not table_name:
            return ""
        name = table_name.strip().strip("`").strip('"').strip()
        if "." in name:
            name = name.split(".")[-1]
        return name.lower()

    def _extract_table_aliases(self, sql: str) -> Dict[str, str]:
        alias_map: Dict[str, str] = {}

        from_pattern = r'\bFROM\s+`?([\w\.]+)`?(?:\s+(?:AS\s+)?`?(\w+)`?)?'
        join_pattern = r'\b(?:LEFT|RIGHT|FULL|INNER|OUTER|CROSS)?\s*JOIN\s+`?([\w\.]+)`?(?:\s+(?:AS\s+)?`?(\w+)`?)?'

        for pattern in (from_pattern, join_pattern):
            for m in re.finditer(pattern, sql, flags=re.IGNORECASE):
                table_raw, alias = m.groups()
                table = self._normalize_table_name(table_raw)
                if not table:
                    continue
                alias_map[table] = table
                if alias:
                    alias_map[alias.strip().lower()] = table

        return alias_map

    def _resolve_table_ref(self, table_ref: str, alias_map: Dict[str, str]) -> str:
        if not table_ref:
            return ""
        key = table_ref.strip().strip("`").strip('"').strip().lower()
        return alias_map.get(key, self._normalize_table_name(key))

    def _extract_on_clauses(self, sql: str) -> List[str]:
        pattern = (
            r'\bON\b\s+(.+?)'
            r'(?=\b(?:LEFT|RIGHT|FULL|INNER|OUTER|CROSS)?\s*JOIN\b|\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b|\bLIMIT\b|\bFETCH\b|\bUNION\b|$)'
        )
        return [m.strip() for m in re.findall(pattern, sql, flags=re.IGNORECASE | re.DOTALL)]

    def _extract_join_equalities(self, sql_fragment: str) -> List[tuple]:
        sql_no_strings = re.sub(r"'[^']*'", '', sql_fragment)
        pattern = r'`?(\w+)`?\.`?(\w+)`?\s*=\s*`?(\w+)`?\.`?(\w+)`?'
        matches = []
        for m in re.finditer(pattern, sql_no_strings, flags=re.IGNORECASE):
            t1, c1, t2, c2 = m.groups()
            matches.append((t1.strip().lower(), c1.strip().lower(), t2.strip().lower(), c2.strip().lower()))
        return matches
    
    def _extract_column_references(self, sql: str) -> List[tuple]:
        """
        从 SQL 中提取列引用
        
        Returns:
            List of (table_ref, column_name) tuples
            table_ref 可能为 None（无表名前缀）
        """
        columns = []
        
        # 匹配 table.column 或 column
        # 排除字符串中的内容
        sql_no_strings = re.sub(r"'[^']*'", '', sql)
        
        # 匹配 table.column
        pattern1 = r'`?(\w+)`?\.`?(\w+)`?'
        for match in re.finditer(pattern1, sql_no_strings):
            table_ref, col_name = match.groups()
            # 排除一些常见的非表名前缀
            if table_ref.upper() not in ('DATE', 'TIME', 'YEAR', 'MONTH', 'DAY'):
                columns.append((table_ref, col_name))
        
        # 匹配 SELECT 后的列名（简化处理）
        select_match = re.search(r'\bSELECT\s+(.*?)\s+FROM\b', sql_no_strings, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_clause = select_match.group(1)
            # 分割列
            for col_expr in select_clause.split(','):
                col_expr = col_expr.strip()
                # 提取列名（排除函数和表达式）
                simple_col = re.match(r'^`?(\w+)`?$', col_expr)
                if simple_col:
                    columns.append((None, simple_col.group(1)))
        
        return columns
    
    def _is_table_alias(self, sql: str, name: str) -> bool:
        """
        检查名称是否是表别名
        
        别名模式：
        - table_name AS alias
        - table_name alias (无 AS 关键字)
        
        但排除：FROM name, JOIN name 等直接引用表名的情况
        """
        # 首先检查是否是直接的表引用（FROM table 或 JOIN table）
        direct_ref_pattern = rf'\b(?:FROM|JOIN)\s+`?{re.escape(name)}`?\b'
        if re.search(direct_ref_pattern, sql, re.IGNORECASE):
            # 这是直接的表引用，不是别名
            return False
        
        # 检查是否作为别名使用（table AS alias 或 table alias）
        # 排除 SQL 关键字作为前缀的情况
        alias_pattern = rf'\b(?!FROM|JOIN|LEFT|RIGHT|INNER|OUTER|CROSS|ON|WHERE|AND|OR|SELECT)\w+\s+(?:AS\s+)?{re.escape(name)}\b'
        return bool(re.search(alias_pattern, sql, re.IGNORECASE))
    
    def _is_sql_function_or_keyword(self, name: str) -> bool:
        """检查是否是 SQL 函数或关键字"""
        functions_and_keywords = {
            'count', 'sum', 'avg', 'max', 'min', 'distinct',
            'case', 'when', 'then', 'else', 'end', 'as',
            'and', 'or', 'not', 'in', 'between', 'like',
            'null', 'true', 'false', 'is', 'asc', 'desc',
            'group', 'order', 'by', 'having', 'where',
            'coalesce', 'ifnull', 'nullif', 'cast', 'convert',
            'date', 'time', 'datetime', 'year', 'month', 'day',
            'now', 'current_date', 'current_time', 'current_timestamp'
        }
        return name.lower() in functions_and_keywords


# 全局单例
sql_validator = SQLValidator()


# 便捷函数
def validate_sql(
    sql: str,
    schema_context: Optional[Dict[str, Any]] = None,
    db_type: str = "mysql"
) -> SQLValidationResult:
    """
    验证 SQL 语句（便捷函数）
    
    Args:
        sql: SQL 语句
        schema_context: Schema 上下文
        db_type: 数据库类型
        
    Returns:
        SQLValidationResult
    """
    return sql_validator.validate(sql, schema_context, db_type)
