"""
分析工具函数模块
提供数据分析、统计计算、异常检测等功能
"""
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def calculate_statistics(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    计算数据的统计信息
    
    Args:
        data: 查询结果数据列表
        
    Returns:
        统计信息字典
    """
    try:
        if not data:
            return {"error": "空数据集"}
        
        df = pd.DataFrame(data)
        
        stats = {
            "total_rows": len(df),
            "columns": list(df.columns),
            "numeric_columns": [],
            "text_columns": [],
            "date_columns": [],
            "summary": {}
        }
        
        # 分类列
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                stats["numeric_columns"].append(col)
                # 数值列统计
                stats["summary"][col] = {
                    "type": "numeric",
                    "count": int(df[col].count()),
                    "mean": float(df[col].mean()) if df[col].count() > 0 else None,
                    "median": float(df[col].median()) if df[col].count() > 0 else None,
                    "min": float(df[col].min()) if df[col].count() > 0 else None,
                    "max": float(df[col].max()) if df[col].count() > 0 else None,
                    "std": float(df[col].std()) if df[col].count() > 1 else None,
                    "sum": float(df[col].sum()) if df[col].count() > 0 else None
                }
            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                stats["date_columns"].append(col)
                stats["summary"][col] = {
                    "type": "datetime",
                    "count": int(df[col].count()),
                    "min": str(df[col].min()) if df[col].count() > 0 else None,
                    "max": str(df[col].max()) if df[col].count() > 0 else None
                }
            else:
                stats["text_columns"].append(col)
                stats["summary"][col] = {
                    "type": "text",
                    "count": int(df[col].count()),
                    "unique": int(df[col].nunique()),
                    "top_values": df[col].value_counts().head(5).to_dict() if df[col].count() > 0 else {}
                }
        
        return stats
        
    except Exception as e:
        return {"error": f"统计计算错误: {str(e)}"}


def detect_time_series(data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    检测数据是否包含时间序列，并识别时间列
    
    Args:
        data: 查询结果数据
        
    Returns:
        时间序列信息或None
    """
    try:
        if not data:
            return None
        
        df = pd.DataFrame(data)
        
        # 尝试识别日期列
        date_columns = []
        for col in df.columns:
            # 尝试转换为日期
            try:
                pd.to_datetime(df[col])
                date_columns.append(col)
            except:
                # 检查列名是否包含日期相关关键词
                if any(keyword in str(col).lower() for keyword in ['date', 'time', 'day', 'month', 'year', '日期', '时间']):
                    try:
                        pd.to_datetime(df[col], errors='coerce')
                        if df[col].notna().sum() > 0:
                            date_columns.append(col)
                    except:
                        pass
        
        if not date_columns:
            return None
        
        # 使用第一个日期列
        date_col = date_columns[0]
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        df = df.sort_values(date_col)
        
        if len(df) < 2:
            return None
        
        return {
            "has_time_series": True,
            "date_column": date_col,
            "date_range": {
                "start": str(df[date_col].min()),
                "end": str(df[date_col].max())
            },
            "data_points": len(df),
            "all_date_columns": date_columns
        }
        
    except Exception as e:
        print(f"时间序列检测错误: {str(e)}")
        return None


def calculate_growth_rate(data: List[Dict[str, Any]], date_col: str, value_col: str) -> Dict[str, Any]:
    """
    计算时间序列数据的增长率
    
    Args:
        data: 数据列表
        date_col: 日期列名
        value_col: 数值列名
        
    Returns:
        增长率分析结果
    """
    try:
        df = pd.DataFrame(data)
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col, value_col])
        df = df.sort_values(date_col)
        
        if len(df) < 2:
            return {"error": "数据点不足，无法计算增长率"}
        
        # 计算环比增长率
        df['growth_rate'] = df[value_col].pct_change() * 100
        
        # 计算总体增长率
        first_value = df[value_col].iloc[0]
        last_value = df[value_col].iloc[-1]
        total_growth = ((last_value - first_value) / first_value * 100) if first_value != 0 else 0
        
        # 平均增长率
        avg_growth = df['growth_rate'].mean() if len(df) > 1 else 0
        
        # 识别趋势
        if total_growth > 10:
            trend = "上升"
        elif total_growth < -10:
            trend = "下降"
        else:
            trend = "平稳"
        
        return {
            "total_growth_rate": float(total_growth),
            "average_growth_rate": float(avg_growth),
            "trend": trend,
            "period_count": len(df),
            "first_value": float(first_value),
            "last_value": float(last_value),
            "max_growth": float(df['growth_rate'].max()) if len(df) > 1 else 0,
            "min_growth": float(df['growth_rate'].min()) if len(df) > 1 else 0
        }
        
    except Exception as e:
        return {"error": f"增长率计算错误: {str(e)}"}


def detect_outliers(data: List[Dict[str, Any]], column: str, method: str = "iqr") -> Dict[str, Any]:
    """
    检测数据中的离群值
    
    Args:
        data: 数据列表
        column: 要检测的列名
        method: 检测方法 ('iqr' 或 'zscore')
        
    Returns:
        离群值检测结果
    """
    try:
        df = pd.DataFrame(data)
        
        if column not in df.columns:
            return {"error": f"列 {column} 不存在"}
        
        if not pd.api.types.is_numeric_dtype(df[column]):
            return {"error": f"列 {column} 不是数值类型"}
        
        values = df[column].dropna()
        
        if len(values) < 4:
            return {"outliers": [], "count": 0}
        
        outliers = []
        
        if method == "iqr":
            # IQR方法
            Q1 = values.quantile(0.25)
            Q3 = values.quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outlier_mask = (values < lower_bound) | (values > upper_bound)
            outliers = values[outlier_mask].tolist()
            
        elif method == "zscore":
            # Z-score方法
            mean = values.mean()
            std = values.std()
            if std > 0:
                z_scores = np.abs((values - mean) / std)
                outlier_mask = z_scores > 3
                outliers = values[outlier_mask].tolist()
        
        return {
            "outliers": [float(x) for x in outliers],
            "count": len(outliers),
            "percentage": (len(outliers) / len(values) * 100) if len(values) > 0 else 0,
            "method": method
        }
        
    except Exception as e:
        return {"error": f"离群值检测错误: {str(e)}"}


def format_insights_for_display(insights: Dict[str, Any]) -> str:
    """
    将洞察结果格式化为易读的文本
    
    Args:
        insights: 洞察结果字典
        
    Returns:
        格式化的文本
    """
    try:
        output = []
        
        # 数据摘要
        if "summary" in insights:
            output.append("📊 数据摘要")
            summary = insights["summary"]
            if "total_rows" in summary:
                output.append(f"  - 总行数: {summary['total_rows']}")
            if "key_metrics" in summary:
                for metric, value in summary["key_metrics"].items():
                    output.append(f"  - {metric}: {value}")
        
        # 趋势分析
        if "trends" in insights and insights["trends"]:
            output.append("\n📈 趋势分析")
            trends = insights["trends"]
            if "trend_direction" in trends:
                output.append(f"  - 整体趋势: {trends['trend_direction']}")
            if "growth_rate" in trends:
                output.append(f"  - 增长率: {trends['growth_rate']:.2f}%")
        
        # 异常检测
        if "anomalies" in insights and insights["anomalies"]:
            output.append("\n⚠️ 异常检测")
            for i, anomaly in enumerate(insights["anomalies"][:3], 1):
                output.append(f"  {i}. {anomaly.get('description', '未知异常')}")
        
        # 业务建议
        if "recommendations" in insights and insights["recommendations"]:
            output.append("\n💡 业务建议")
            for i, rec in enumerate(insights["recommendations"][:3], 1):
                output.append(f"  {i}. {rec}")
        
        return "\n".join(output) if output else "暂无分析洞察"
        
    except Exception as e:
        return f"格式化错误: {str(e)}"


def analyze_distribution(data: List[Dict[str, Any]], column: str) -> Dict[str, Any]:
    """
    分析数值列的分布情况
    
    Args:
        data: 数据列表
        column: 列名
        
    Returns:
        分布分析结果
    """
    try:
        df = pd.DataFrame(data)
        
        if column not in df.columns:
            return {"error": f"列 {column} 不存在"}
        
        if not pd.api.types.is_numeric_dtype(df[column]):
            return {"error": f"列 {column} 不是数值类型"}
        
        values = df[column].dropna()
        
        if len(values) == 0:
            return {"error": "没有有效数据"}
        
        # 计算分位数
        quartiles = {
            "q25": float(values.quantile(0.25)),
            "q50": float(values.quantile(0.50)),
            "q75": float(values.quantile(0.75))
        }
        
        # 偏度和峰度
        skewness = float(values.skew())
        kurtosis = float(values.kurt())
        
        # 分布类型判断
        if abs(skewness) < 0.5:
            distribution_type = "近似正态分布"
        elif skewness > 0.5:
            distribution_type = "右偏分布"
        else:
            distribution_type = "左偏分布"
        
        return {
            "quartiles": quartiles,
            "skewness": skewness,
            "kurtosis": kurtosis,
            "distribution_type": distribution_type,
            "range": float(values.max() - values.min())
        }
        
    except Exception as e:
        return {"error": f"分布分析错误: {str(e)}"}


def find_correlations(data: List[Dict[str, Any]], threshold: float = 0.5) -> Dict[str, Any]:
    """
    查找数值列之间的相关性
    
    Args:
        data: 数据列表
        threshold: 相关性阈值
        
    Returns:
        相关性分析结果
    """
    try:
        df = pd.DataFrame(data)
        
        # 只选择数值列
        numeric_df = df.select_dtypes(include=[np.number])
        
        if numeric_df.shape[1] < 2:
            return {"correlations": [], "message": "数值列少于2个，无法计算相关性"}
        
        # 计算相关性矩阵
        corr_matrix = numeric_df.corr()
        
        # 提取强相关性
        strong_correlations = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                corr_value = corr_matrix.iloc[i, j]
                if abs(corr_value) >= threshold:
                    strong_correlations.append({
                        "column1": corr_matrix.columns[i],
                        "column2": corr_matrix.columns[j],
                        "correlation": float(corr_value),
                        "strength": "强正相关" if corr_value > threshold else "强负相关"
                    })
        
        return {
            "correlations": strong_correlations,
            "count": len(strong_correlations),
            "threshold": threshold
        }
        
    except Exception as e:
        return {"error": f"相关性分析错误: {str(e)}"}
