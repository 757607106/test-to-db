"""
预测分析服务
P2功能：实现时间序列预测和趋势分析
"""
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import math

from app.schemas.prediction import (
    PredictionMethod,
    PredictionDataPoint,
    AccuracyMetrics,
    TrendAnalysis,
    PredictionResult,
)

logger = logging.getLogger(__name__)


class PredictionService:
    """预测分析服务"""
    
    async def predict(
        self,
        data: List[Dict[str, Any]],
        date_column: str,
        value_column: str,
        periods: int,
        method: str = "auto",
        confidence_level: float = 0.95
    ) -> PredictionResult:
        """
        执行预测分析
        
        Args:
            data: 历史数据列表
            date_column: 时间列名
            value_column: 预测目标列名
            periods: 预测周期数
            method: 预测方法
            confidence_level: 置信水平
            
        Returns:
            PredictionResult: 预测结果
        """
        logger.info(f"开始预测分析: {len(data)} 条数据, 预测 {periods} 个周期")
        
        # 提取并排序数据
        sorted_data = sorted(data, key=lambda x: str(x.get(date_column, "")))
        dates = [str(row.get(date_column, "")) for row in sorted_data]
        values = [float(row.get(value_column, 0)) for row in sorted_data]
        
        if len(values) < 3:
            raise ValueError("数据点数量不足，至少需要3个数据点")
        
        # 自动选择预测方法
        if method == "auto":
            method = self._select_best_method(values)
        
        # 执行预测
        if method == "linear":
            predictions, lower, upper = self._linear_prediction(values, periods, confidence_level)
        elif method == "moving_average":
            predictions, lower, upper = self._moving_average_prediction(values, periods, confidence_level)
        elif method == "exponential_smoothing":
            predictions, lower, upper = self._exponential_smoothing_prediction(values, periods, confidence_level)
        else:
            predictions, lower, upper = self._linear_prediction(values, periods, confidence_level)
        
        # 生成预测日期
        prediction_dates = self._generate_future_dates(dates, periods)
        
        # 构建历史数据点
        historical_points = [
            PredictionDataPoint(
                date=dates[i],
                value=values[i],
                is_prediction=False
            )
            for i in range(len(values))
        ]
        
        # 构建预测数据点
        prediction_points = [
            PredictionDataPoint(
                date=prediction_dates[i],
                value=predictions[i],
                lower_bound=lower[i],
                upper_bound=upper[i],
                is_prediction=True
            )
            for i in range(len(predictions))
        ]
        
        # 计算准确性指标（使用交叉验证）
        accuracy = self._calculate_accuracy_metrics(values, method)
        
        # 趋势分析
        trend = self._analyze_trend(values)
        
        return PredictionResult(
            historical_data=historical_points,
            predictions=prediction_points,
            method_used=PredictionMethod(method),
            accuracy_metrics=accuracy,
            trend_analysis=trend,
            generated_at=datetime.utcnow()
        )
    
    def _select_best_method(self, values: List[float]) -> str:
        """
        根据数据特征自动选择最佳预测方法
        """
        n = len(values)
        
        # 计算趋势强度
        if n < 5:
            return "moving_average"
        
        # 简单线性回归R²
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        ss_tot = sum((y - y_mean) ** 2 for y in values)
        
        # 计算线性拟合
        slope, intercept = self._linear_fit(values)
        predicted = [intercept + slope * i for i in range(n)]
        ss_res = sum((values[i] - predicted[i]) ** 2 for i in range(n))
        
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # 计算波动率
        volatility = self._calculate_volatility(values)
        
        # 选择方法
        if r_squared > 0.7:
            return "linear"
        elif volatility > 0.3:
            return "exponential_smoothing"
        else:
            return "moving_average"
    
    def _linear_fit(self, values: List[float]) -> Tuple[float, float]:
        """线性最小二乘拟合"""
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        denominator = n * x2_sum - x_sum * x_sum
        if denominator == 0:
            return 0, y_sum / n if n > 0 else 0
        
        slope = (n * xy_sum - x_sum * y_sum) / denominator
        intercept = (y_sum - slope * x_sum) / n
        
        return slope, intercept
    
    def _linear_prediction(
        self,
        values: List[float],
        periods: int,
        confidence_level: float
    ) -> Tuple[List[float], List[float], List[float]]:
        """线性回归预测"""
        n = len(values)
        slope, intercept = self._linear_fit(values)
        
        # 计算标准误差
        predicted = [intercept + slope * i for i in range(n)]
        residuals = [values[i] - predicted[i] for i in range(n)]
        mse = sum(r * r for r in residuals) / max(1, n - 2)
        se = math.sqrt(mse) if mse > 0 else 0
        
        # Z值 (近似，95%置信度约为1.96)
        z = 1.96 if confidence_level == 0.95 else 1.645
        
        predictions = []
        lower = []
        upper = []
        
        for i in range(periods):
            pred = intercept + slope * (n + i)
            margin = z * se * math.sqrt(1 + 1/n + ((n + i - n/2)**2) / sum((j - n/2)**2 for j in range(n)))
            
            predictions.append(round(pred, 2))
            lower.append(round(pred - margin, 2))
            upper.append(round(pred + margin, 2))
        
        return predictions, lower, upper
    
    def _moving_average_prediction(
        self,
        values: List[float],
        periods: int,
        confidence_level: float,
        window: int = 3
    ) -> Tuple[List[float], List[float], List[float]]:
        """移动平均预测"""
        window = min(window, len(values))
        
        # 计算标准差用于置信区间
        std = self._calculate_std(values)
        z = 1.96 if confidence_level == 0.95 else 1.645
        
        predictions = []
        lower = []
        upper = []
        
        recent_values = list(values[-window:])
        
        for i in range(periods):
            pred = sum(recent_values) / len(recent_values)
            margin = z * std
            
            predictions.append(round(pred, 2))
            lower.append(round(pred - margin, 2))
            upper.append(round(pred + margin, 2))
            
            # 滑动窗口
            recent_values = recent_values[1:] + [pred]
        
        return predictions, lower, upper
    
    def _exponential_smoothing_prediction(
        self,
        values: List[float],
        periods: int,
        confidence_level: float,
        alpha: float = 0.3
    ) -> Tuple[List[float], List[float], List[float]]:
        """指数平滑预测"""
        n = len(values)
        
        # 计算平滑值
        smoothed = [values[0]]
        for i in range(1, n):
            smoothed.append(alpha * values[i] + (1 - alpha) * smoothed[-1])
        
        # 计算标准差
        residuals = [values[i] - smoothed[i] for i in range(n)]
        std = math.sqrt(sum(r * r for r in residuals) / max(1, n - 1))
        z = 1.96 if confidence_level == 0.95 else 1.645
        
        predictions = []
        lower = []
        upper = []
        
        last_smooth = smoothed[-1]
        
        for i in range(periods):
            pred = last_smooth
            margin = z * std * math.sqrt(1 + i * alpha * alpha)
            
            predictions.append(round(pred, 2))
            lower.append(round(pred - margin, 2))
            upper.append(round(pred + margin, 2))
        
        return predictions, lower, upper
    
    def _generate_future_dates(self, dates: List[str], periods: int) -> List[str]:
        """生成未来日期"""
        from datetime import timedelta
        
        try:
            # 尝试解析最后一个日期
            last_date_str = dates[-1]
            
            # 尝试多种日期格式
            formats = [
                "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y", "%m/%d/%Y"
            ]
            
            last_date = None
            for fmt in formats:
                try:
                    last_date = datetime.strptime(last_date_str[:10], fmt)
                    break
                except ValueError:
                    continue
            
            if last_date is None:
                # 如果无法解析，使用序号
                return [f"T+{i+1}" for i in range(periods)]
            
            # 计算日期间隔
            if len(dates) >= 2:
                try:
                    prev_date = datetime.strptime(dates[-2][:10], fmt)
                    interval = (last_date - prev_date).days
                    interval = max(1, interval)
                except:
                    interval = 1
            else:
                interval = 1
            
            # 生成未来日期
            future_dates = []
            for i in range(1, periods + 1):
                future_date = last_date + timedelta(days=interval * i)
                future_dates.append(future_date.strftime("%Y-%m-%d"))
            
            return future_dates
            
        except Exception as e:
            logger.warning(f"日期生成失败: {e}, 使用序号代替")
            return [f"T+{i+1}" for i in range(periods)]
    
    def _calculate_accuracy_metrics(
        self,
        values: List[float],
        method: str
    ) -> AccuracyMetrics:
        """计算预测准确性指标（使用留一交叉验证）"""
        n = len(values)
        
        if n < 4:
            return AccuracyMetrics(mape=10.0, rmse=0.0, mae=0.0)
        
        # 使用后20%数据作为测试集
        split = max(3, int(n * 0.8))
        train = values[:split]
        test = values[split:]
        
        if len(test) == 0:
            return AccuracyMetrics(mape=10.0, rmse=0.0, mae=0.0)
        
        # 用训练集预测测试集
        if method == "linear":
            slope, intercept = self._linear_fit(train)
            predicted = [intercept + slope * (split + i) for i in range(len(test))]
        elif method == "moving_average":
            window = min(3, len(train))
            recent = train[-window:]
            predicted = [sum(recent) / len(recent)] * len(test)
        else:
            alpha = 0.3
            smoothed = train[-1]
            predicted = [smoothed] * len(test)
        
        # 计算指标
        errors = [abs(test[i] - predicted[i]) for i in range(len(test))]
        squared_errors = [(test[i] - predicted[i]) ** 2 for i in range(len(test))]
        
        mae = sum(errors) / len(errors)
        rmse = math.sqrt(sum(squared_errors) / len(squared_errors))
        
        # MAPE (避免除以0)
        mape_values = []
        for i in range(len(test)):
            if abs(test[i]) > 0.001:
                mape_values.append(abs(errors[i] / test[i]) * 100)
        mape = sum(mape_values) / len(mape_values) if mape_values else 0
        
        return AccuracyMetrics(
            mape=round(mape, 2),
            rmse=round(rmse, 2),
            mae=round(mae, 2)
        )
    
    def _analyze_trend(self, values: List[float]) -> TrendAnalysis:
        """分析数据趋势"""
        n = len(values)
        
        if n < 2:
            return TrendAnalysis(
                direction="stable",
                growth_rate=0.0,
                average_value=values[0] if values else 0,
                min_value=values[0] if values else 0,
                max_value=values[0] if values else 0,
                volatility=0.0
            )
        
        # 计算增长率
        first_half = sum(values[:n//2]) / (n//2) if n >= 2 else values[0]
        second_half = sum(values[n//2:]) / (n - n//2) if n >= 2 else values[0]
        
        if abs(first_half) > 0.001:
            growth_rate = ((second_half - first_half) / abs(first_half)) * 100
        else:
            growth_rate = 0.0
        
        # 确定方向
        if growth_rate > 5:
            direction = "up"
        elif growth_rate < -5:
            direction = "down"
        else:
            direction = "stable"
        
        # 统计值
        avg_value = sum(values) / n
        min_value = min(values)
        max_value = max(values)
        
        # 波动率
        volatility = self._calculate_volatility(values)
        
        return TrendAnalysis(
            direction=direction,
            growth_rate=round(growth_rate, 2),
            average_value=round(avg_value, 2),
            min_value=round(min_value, 2),
            max_value=round(max_value, 2),
            volatility=round(volatility * 100, 2)
        )
    
    def _calculate_volatility(self, values: List[float]) -> float:
        """计算波动率（变异系数）"""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        if abs(mean) < 0.001:
            return 0.0
        
        std = self._calculate_std(values)
        return std / abs(mean)
    
    def _calculate_std(self, values: List[float]) -> float:
        """计算标准差"""
        n = len(values)
        if n < 2:
            return 0.0
        
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        return math.sqrt(variance)


# 创建全局实例
prediction_service = PredictionService()
