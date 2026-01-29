"""
库存分析服务
商业级库存分析引擎：ABC-XYZ分类、周转率分析、安全库存计算、供应商评估
基于统计学方法实现，确保分析结果准确可靠
"""
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from app.schemas.inventory_analysis import (
    ABCXYZRequest, ABCXYZResult, ABCXYZSummary, ABCXYZMatrix, ABCXYZDetail,
    ParetoData, ABCClassSummary,
    TurnoverRequest, TurnoverResult, TurnoverDetail, TurnoverSummary,
    SafetyStockRequest, SafetyStockResult, SafetyStockDetail, SafetyStockSummary,
    SupplierEvaluationRequest, SupplierResult, SupplierDetail, SupplierSummary,
)

logger = logging.getLogger(__name__)


class InventoryAnalysisService:
    """库存分析服务"""
    
    # ==================== ABC-XYZ 分析 ====================
    
    def abc_xyz_analysis(
        self,
        data: List[Dict[str, Any]],
        product_column: str,
        value_column: str,
        quantity_column: str,
        abc_thresholds: List[float] = None,
        xyz_thresholds: List[float] = None
    ) -> ABCXYZResult:
        """
        ABC-XYZ 库存分类分析
        
        ABC分类（帕累托分析）：
        - A类：累计贡献前70%的产品（高价值）
        - B类：累计贡献70%-90%的产品（中价值）
        - C类：累计贡献90%-100%的产品（低价值）
        
        XYZ分类（需求稳定性，基于变异系数CV）：
        - X类：CV < 0.5（稳定）
        - Y类：0.5 <= CV < 1.0（波动）
        - Z类：CV >= 1.0（不稳定）
        
        Args:
            data: 原始数据列表
            product_column: 产品标识列名
            value_column: 价值列名
            quantity_column: 数量列名
            abc_thresholds: ABC阈值，默认 [0.7, 0.9]
            xyz_thresholds: XYZ阈值（变异系数），默认 [0.5, 1.0]
            
        Returns:
            ABCXYZResult: 分析结果
        """
        logger.info(f"[ABC-XYZ] 开始分析，数据量: {len(data)}")
        
        if not abc_thresholds:
            abc_thresholds = [0.7, 0.9]
        if not xyz_thresholds:
            xyz_thresholds = [0.5, 1.0]
        
        df = pd.DataFrame(data)
        
        # 确保数值列为数值类型
        df[value_column] = pd.to_numeric(df[value_column], errors='coerce').fillna(0)
        df[quantity_column] = pd.to_numeric(df[quantity_column], errors='coerce').fillna(0)
        
        # 1. 按产品聚合
        product_agg = df.groupby(product_column).agg({
            value_column: 'sum',
            quantity_column: ['sum', 'mean', 'std', 'count']
        }).reset_index()
        
        # 展平列名
        product_agg.columns = [
            product_column, 'total_value', 'total_quantity', 
            'avg_quantity', 'std_quantity', 'period_count'
        ]
        
        # 2. ABC 分类（帕累托分析）
        product_agg = product_agg.sort_values('total_value', ascending=False)
        total_value = product_agg['total_value'].sum()
        
        if total_value > 0:
            product_agg['value_pct'] = product_agg['total_value'] / total_value
            product_agg['cumulative_pct'] = product_agg['value_pct'].cumsum()
        else:
            product_agg['value_pct'] = 0
            product_agg['cumulative_pct'] = 0
        
        # ABC 分类
        def classify_abc(cum_pct):
            if cum_pct <= abc_thresholds[0]:
                return 'A'
            elif cum_pct <= abc_thresholds[1]:
                return 'B'
            else:
                return 'C'
        
        product_agg['abc_class'] = product_agg['cumulative_pct'].apply(classify_abc)
        
        # 3. XYZ 分类（变异系数）
        def calculate_cv(row):
            """计算变异系数 CV = 标准差 / 均值"""
            if row['avg_quantity'] > 0 and not pd.isna(row['std_quantity']):
                return row['std_quantity'] / row['avg_quantity']
            return 0  # 无波动
        
        product_agg['cv'] = product_agg.apply(calculate_cv, axis=1)
        
        def classify_xyz(cv):
            if cv < xyz_thresholds[0]:
                return 'X'
            elif cv < xyz_thresholds[1]:
                return 'Y'
            else:
                return 'Z'
        
        product_agg['xyz_class'] = product_agg['cv'].apply(classify_xyz)
        product_agg['combined_class'] = product_agg['abc_class'] + product_agg['xyz_class']
        
        # 4. 构建结果
        # 汇总统计
        total_products = len(product_agg)
        
        def get_class_summary(df_class, total_val, total_prod):
            count = len(df_class)
            value = df_class['total_value'].sum()
            return ABCClassSummary(
                count=count,
                value=round(value, 2),
                pct=round(value / total_val * 100, 2) if total_val > 0 else 0,
                product_pct=round(count / total_prod * 100, 2) if total_prod > 0 else 0
            )
        
        summary = ABCXYZSummary(
            total_products=total_products,
            total_value=round(total_value, 2),
            a_class=get_class_summary(product_agg[product_agg['abc_class'] == 'A'], total_value, total_products),
            b_class=get_class_summary(product_agg[product_agg['abc_class'] == 'B'], total_value, total_products),
            c_class=get_class_summary(product_agg[product_agg['abc_class'] == 'C'], total_value, total_products)
        )
        
        # 9宫格矩阵
        matrix_data = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        matrix_values = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        abc_map = {'A': 0, 'B': 1, 'C': 2}
        xyz_map = {'X': 0, 'Y': 1, 'Z': 2}
        
        for _, row in product_agg.iterrows():
            i = abc_map[row['abc_class']]
            j = xyz_map[row['xyz_class']]
            matrix_data[i][j] += 1
            matrix_values[i][j] += row['total_value']
        
        matrix_pct = [
            [round(c / total_products * 100, 2) if total_products > 0 else 0 for c in row]
            for row in matrix_data
        ]
        matrix_values = [[round(v, 2) for v in row] for row in matrix_values]
        
        matrix = ABCXYZMatrix(
            rows=['A', 'B', 'C'],
            cols=['X', 'Y', 'Z'],
            data=matrix_data,
            percentages=matrix_pct,
            values=matrix_values
        )
        
        # 帕累托图数据
        pareto = ParetoData(
            labels=product_agg[product_column].tolist(),
            values=[round(v, 2) for v in product_agg['total_value'].tolist()],
            cumulative_pct=[round(p, 4) for p in product_agg['cumulative_pct'].tolist()],
            abc_class=product_agg['abc_class'].tolist()
        )
        
        # 详细列表
        details = [
            ABCXYZDetail(
                product_id=str(row[product_column]),
                value=round(row['total_value'], 2),
                quantity=round(row['total_quantity'], 2),
                cumulative_pct=round(row['cumulative_pct'], 4),
                cv=round(row['cv'], 4),
                abc_class=row['abc_class'],
                xyz_class=row['xyz_class'],
                combined_class=row['combined_class']
            )
            for _, row in product_agg.iterrows()
        ]
        
        logger.info(f"[ABC-XYZ] 分析完成，产品数: {total_products}")
        
        return ABCXYZResult(
            summary=summary,
            matrix=matrix,
            pareto=pareto,
            details=details,
            statistical_basis={
                "abc_method": "帕累托分析（Pareto Analysis）",
                "abc_thresholds": abc_thresholds,
                "xyz_method": "变异系数分析（Coefficient of Variation）",
                "xyz_thresholds": xyz_thresholds,
                "cv_formula": "CV = σ / μ (标准差 / 均值)"
            }
        )
    
    # ==================== 库存周转率分析 ====================
    
    def inventory_turnover(
        self,
        data: List[Dict[str, Any]],
        product_column: str,
        cogs_column: str,
        inventory_column: str,
        good_threshold: float = 30,
        warning_threshold: float = 90
    ) -> TurnoverResult:
        """
        库存周转率分析
        
        周转率 = 销售成本 / 平均库存
        库存天数 = 365 / 周转率
        
        Args:
            data: 原始数据列表
            product_column: 产品标识列名
            cogs_column: 销售成本列名
            inventory_column: 库存价值列名
            good_threshold: 健康阈值（天）
            warning_threshold: 警告阈值（天）
            
        Returns:
            TurnoverResult: 分析结果
        """
        logger.info(f"[周转率] 开始分析，数据量: {len(data)}")
        
        df = pd.DataFrame(data)
        
        # 确保数值类型
        df[cogs_column] = pd.to_numeric(df[cogs_column], errors='coerce').fillna(0)
        df[inventory_column] = pd.to_numeric(df[inventory_column], errors='coerce').fillna(0)
        
        # 按产品聚合
        product_agg = df.groupby(product_column).agg({
            cogs_column: 'sum',
            inventory_column: 'mean'
        }).reset_index()
        
        product_agg.columns = [product_column, 'cogs', 'avg_inventory']
        
        # 计算周转率
        def calc_turnover(row):
            if row['avg_inventory'] > 0:
                return row['cogs'] / row['avg_inventory']
            return 0
        
        product_agg['turnover_rate'] = product_agg.apply(calc_turnover, axis=1)
        product_agg['days_in_inventory'] = product_agg['turnover_rate'].apply(
            lambda x: 365 / x if x > 0 else 999
        )
        
        # 健康度评估
        def assess_health(days):
            if days <= good_threshold:
                return 'good'
            elif days <= warning_threshold:
                return 'warning'
            else:
                return 'critical'
        
        product_agg['health'] = product_agg['days_in_inventory'].apply(assess_health)
        
        # 构建结果
        details = [
            TurnoverDetail(
                product_id=str(row[product_column]),
                cogs=round(row['cogs'], 2),
                avg_inventory=round(row['avg_inventory'], 2),
                turnover_rate=round(row['turnover_rate'], 2),
                days_in_inventory=round(row['days_in_inventory'], 1),
                health=row['health']
            )
            for _, row in product_agg.iterrows()
        ]
        
        # 汇总
        valid_turnover = product_agg[product_agg['turnover_rate'] > 0]
        
        summary = TurnoverSummary(
            total_products=len(product_agg),
            avg_turnover_rate=round(valid_turnover['turnover_rate'].mean(), 2) if len(valid_turnover) > 0 else 0,
            avg_days_in_inventory=round(valid_turnover['days_in_inventory'].mean(), 1) if len(valid_turnover) > 0 else 0,
            good_count=len(product_agg[product_agg['health'] == 'good']),
            warning_count=len(product_agg[product_agg['health'] == 'warning']),
            critical_count=len(product_agg[product_agg['health'] == 'critical'])
        )
        
        logger.info(f"[周转率] 分析完成，产品数: {len(product_agg)}")
        
        return TurnoverResult(
            summary=summary,
            details=details,
            thresholds={"good": good_threshold, "warning": warning_threshold}
        )
    
    # ==================== 安全库存计算 ====================
    
    def safety_stock(
        self,
        data: List[Dict[str, Any]],
        product_column: str,
        demand_column: str,
        lead_time: float,
        service_level: float = 0.95
    ) -> SafetyStockResult:
        """
        安全库存计算
        
        公式：安全库存 = Z × σ_demand × √(LT)
        - Z: 服务水平对应的标准正态分位数
        - σ_demand: 需求标准差
        - LT: 前置时间（天）
        
        再订货点 = 平均需求 × 前置时间 + 安全库存
        
        Args:
            data: 原始数据列表
            product_column: 产品标识列名
            demand_column: 需求量列名
            lead_time: 前置时间（天）
            service_level: 服务水平（0-1）
            
        Returns:
            SafetyStockResult: 计算结果
        """
        logger.info(f"[安全库存] 开始计算，服务水平: {service_level}, 前置时间: {lead_time}")
        
        df = pd.DataFrame(data)
        df[demand_column] = pd.to_numeric(df[demand_column], errors='coerce').fillna(0)
        
        # 按产品聚合需求统计
        product_agg = df.groupby(product_column)[demand_column].agg(['mean', 'std', 'count']).reset_index()
        product_agg.columns = [product_column, 'avg_demand', 'demand_std', 'period_count']
        product_agg['demand_std'] = product_agg['demand_std'].fillna(0)
        
        # 计算 Z 值
        z_score = stats.norm.ppf(service_level)
        
        # 计算安全库存和再订货点
        sqrt_lt = np.sqrt(lead_time)
        
        details = []
        total_safety = 0
        total_rop = 0
        
        for _, row in product_agg.iterrows():
            safety = z_score * row['demand_std'] * sqrt_lt
            rop = row['avg_demand'] * lead_time + safety
            
            total_safety += safety
            total_rop += rop
            
            details.append(SafetyStockDetail(
                product_id=str(row[product_column]),
                avg_demand=round(row['avg_demand'], 2),
                demand_std=round(row['demand_std'], 2),
                safety_stock=round(safety, 0),
                reorder_point=round(rop, 0)
            ))
        
        summary = SafetyStockSummary(
            total_products=len(product_agg),
            total_safety_stock=round(total_safety, 0),
            total_reorder_point=round(total_rop, 0),
            service_level=f"{service_level * 100:.0f}%"
        )
        
        logger.info(f"[安全库存] 计算完成，产品数: {len(product_agg)}")
        
        return SafetyStockResult(
            summary=summary,
            details=details,
            statistical_basis={
                "formula": "安全库存 = Z × σ × √(LT)",
                "z_score": round(z_score, 4),
                "lead_time": lead_time,
                "service_level": service_level,
                "distribution": "正态分布假设"
            }
        )
    
    # ==================== 供应商评估 ====================
    
    def supplier_evaluation(
        self,
        data: List[Dict[str, Any]],
        supplier_column: str,
        metrics_columns: List[str],
        weights: Optional[List[float]] = None,
        n_clusters: int = 3
    ) -> SupplierResult:
        """
        供应商评估
        
        使用加权评分法 + K-means 聚类
        
        Args:
            data: 原始数据列表
            supplier_column: 供应商标识列名
            metrics_columns: 评估指标列名列表
            weights: 指标权重（默认等权）
            n_clusters: 聚类数量
            
        Returns:
            SupplierResult: 评估结果
        """
        logger.info(f"[供应商评估] 开始分析，指标: {metrics_columns}")
        
        df = pd.DataFrame(data)
        
        # 确保数值类型
        for col in metrics_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 按供应商聚合
        supplier_agg = df.groupby(supplier_column)[metrics_columns].mean().reset_index()
        
        # 设置权重
        if weights is None:
            weights = [1.0 / len(metrics_columns)] * len(metrics_columns)
        
        weights_dict = dict(zip(metrics_columns, weights))
        
        # 标准化（Min-Max）
        normalized = supplier_agg.copy()
        for col in metrics_columns:
            min_val = supplier_agg[col].min()
            max_val = supplier_agg[col].max()
            if max_val > min_val:
                normalized[f'{col}_norm'] = (supplier_agg[col] - min_val) / (max_val - min_val)
            else:
                normalized[f'{col}_norm'] = 0.5
        
        # 计算加权得分
        normalized['weighted_score'] = sum(
            normalized[f'{col}_norm'] * weight 
            for col, weight in weights_dict.items()
        )
        
        # K-means 聚类
        cluster_labels = None
        if len(supplier_agg) >= n_clusters:
            features = normalized[[f'{col}_norm' for col in metrics_columns]].values
            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)
            
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(features_scaled)
            normalized['cluster'] = cluster_labels
        
        # 排名
        normalized = normalized.sort_values('weighted_score', ascending=False)
        normalized['rank'] = range(1, len(normalized) + 1)
        
        # 构建结果
        details = []
        for _, row in normalized.iterrows():
            metrics_values = {col: round(row[col], 2) for col in metrics_columns}
            normalized_values = {col: round(row[f'{col}_norm'], 4) for col in metrics_columns}
            
            details.append(SupplierDetail(
                supplier_id=str(row[supplier_column]),
                metrics=metrics_values,
                normalized_metrics=normalized_values,
                weighted_score=round(row['weighted_score'], 4),
                rank=row['rank'],
                cluster=int(row['cluster']) if cluster_labels is not None else None
            ))
        
        summary = SupplierSummary(
            total_suppliers=len(supplier_agg),
            avg_score=round(normalized['weighted_score'].mean(), 4),
            top_supplier=str(normalized.iloc[0][supplier_column]) if len(normalized) > 0 else "",
            cluster_count=n_clusters if cluster_labels is not None else None
        )
        
        logger.info(f"[供应商评估] 分析完成，供应商数: {len(supplier_agg)}")
        
        return SupplierResult(
            summary=summary,
            details=details,
            weights_used=weights_dict
        )


# 创建全局实例
inventory_analysis_service = InventoryAnalysisService()
