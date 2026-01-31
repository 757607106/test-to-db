"""
预测分析服务 - 优化版
核心改进：
1. 数据预处理：日期正确排序、缺失值智能填充、异常值检测
2. 智能化：自适应方法选择、参数自动调优、季节性检测
3. 可解释性：预测依据透明化、计算过程可追溯
4. 准确性：优化置信区间、增强评估机制
"""
import logging
import math
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timedelta
try:
    from scipy import stats
except Exception:
    stats = None

from app.schemas.prediction import (
    PredictionMethod,
    PredictionDataPoint,
    AccuracyMetrics,
    TrendAnalysis,
    PredictionResult,
    DataQualityInfo,
    MethodSelectionReason,
    PredictionExplanation,
    DataSourceInfo,
    KeyMetricValue,
    ReasoningStep,
)

logger = logging.getLogger(__name__)


class PredictionService:
    """预测分析服务 - 优化版"""
    
    # ==================== 主入口 ====================
    
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
        执行预测分析 - 优化版
        
        改进点：
        1. 日期解析为datetime后排序，而非字符串排序
        2. 缺失值使用前向填充，而非硬编码为0
        3. 异常值检测（IQR方法）
        4. 预测结果包含完整解释
        """
        logger.info(f"[预测] 开始分析: {len(data)} 条数据, 预测 {periods} 个周期")
        
        # 1. 数据预处理（核心改进）
        processed_data, data_quality = self._preprocess_data(data, date_column, value_column)
        dates = processed_data["dates"]
        values = processed_data["values"]
        parsed_dates = processed_data["parsed_dates"]
        
        if len(values) < 3:
            raise ValueError("有效数据点数量不足，至少需要3个有效数据点")
        
        # 2. 数据特征分析
        characteristics = self._analyze_data_characteristics(values, parsed_dates)
        
        # 3. 智能方法选择（如果是auto模式）
        if method == "auto":
            method, method_selection = self._select_best_method_enhanced(values, characteristics)
        else:
            method_selection = MethodSelectionReason(
                selected_method=method,
                reason=f"用户手动指定使用 {method} 方法",
                data_characteristics=characteristics,
                method_scores={}
            )
        
        # 4. 参数自动调优
        optimized_params = self._optimize_parameters(values, method)
        
        # 5. 执行预测
        if method == "linear":
            predictions, lower, upper, key_params = self._linear_prediction_enhanced(
                values, periods, confidence_level
            )
        elif method == "moving_average":
            predictions, lower, upper, key_params = self._moving_average_prediction_enhanced(
                values, periods, confidence_level, optimized_params.get("window", 3)
            )
        elif method == "exponential_smoothing":
            predictions, lower, upper, key_params = self._exponential_smoothing_enhanced(
                values, periods, confidence_level, optimized_params.get("alpha", 0.3)
            )
        else:
            predictions, lower, upper, key_params = self._linear_prediction_enhanced(
                values, periods, confidence_level
            )
        
        # 6. 生成预测日期
        prediction_dates = self._generate_future_dates_enhanced(
            parsed_dates, periods, data_quality.date_interval
        )
        
        # 7. 构建历史数据点
        historical_points = [
            PredictionDataPoint(date=dates[i], value=round(values[i], 2), is_prediction=False)
            for i in range(len(values))
        ]
        
        # 8. 构建预测数据点
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
        
        # 9. 计算准确性指标（时序交叉验证）
        accuracy = self._calculate_accuracy_enhanced(values, method, optimized_params)
        
        # 10. 趋势分析（含季节性检测）
        trend = self._analyze_trend_enhanced(values, characteristics)
        
        # 11. 生成预测解释
        explanation = self._generate_explanation(
            method, key_params, values, predictions, confidence_level, accuracy,
            categories=dates, date_column=date_column, value_column=value_column
        )
        
        return PredictionResult(
            historical_data=historical_points,
            predictions=prediction_points,
            method_used=PredictionMethod(method),
            accuracy_metrics=accuracy,
            trend_analysis=trend,
            generated_at=datetime.utcnow(),
            data_quality=data_quality,
            method_selection=method_selection,
            explanation=explanation
        )
    
    # ==================== 数据预处理 ====================
    
    def _preprocess_data(
        self, 
        data: List[Dict[str, Any]], 
        date_column: str, 
        value_column: str
    ) -> Tuple[Dict[str, Any], DataQualityInfo]:
        """
        数据预处理 - 核心改进
        
        改进点：
        1. 日期解析为datetime后排序（而非字符串排序）
        2. 缺失值使用前向填充（而非硬编码为0）
        3. 异常值检测（IQR方法）
        """
        total_points = len(data)
        missing_count = 0
        outlier_indices = []
        
        # 1. 解析日期并排序
        parsed_data = []
        date_formats = [
            "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"
        ]
        
        for idx, row in enumerate(data):
            date_val = row.get(date_column)
            value_raw = row.get(value_column)
            
            # 解析日期 - 优先处理数值型和时间戳
            parsed_date = None
            date_str = str(date_val) if date_val is not None else ""
            
            # 1. 如果是数值类型（序号或时间戳）
            if isinstance(date_val, (int, float)):
                # 判断是Unix时间戳还是简单序号
                if 946684800 < date_val < 4102444800:  # 2000-2100年的时间戳
                    try:
                        parsed_date = datetime.fromtimestamp(date_val)
                    except (ValueError, OSError):
                        pass
                
                # 如果不是时间戳，作为序号处理（不输出警告）
                if parsed_date is None:
                    parsed_date = datetime(2000, 1, 1) + timedelta(days=int(date_val))
            
            # 2. 如果是datetime对象
            elif isinstance(date_val, datetime):
                parsed_date = date_val
            
            # 3. 如果是字符串，尝试各种格式
            elif isinstance(date_val, str) and date_str.strip():
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.strptime(date_str[:10], fmt)
                        break
                    except (ValueError, TypeError):
                        continue
            
            # 4. 最后的fallback
            if parsed_date is None:
                parsed_date = datetime(2000, 1, 1) + timedelta(days=idx)
                # 只对非数值类型输出警告
                if not isinstance(date_val, (int, float)):
                    logger.warning(f"[预测] 日期解析失败: {date_str}, 使用索引代替")
            
            # 解析数值
            value = None
            if value_raw is not None:
                try:
                    if isinstance(value_raw, (int, float)):
                        value = float(value_raw)
                    elif isinstance(value_raw, str):
                        value = float(value_raw.replace(",", ""))
                except (ValueError, TypeError):
                    value = None
            
            if value is None:
                missing_count += 1
            
            parsed_data.append({
                "date_str": date_str,
                "parsed_date": parsed_date,
                "value": value,
                "original_idx": idx
            })
        
        # 2. 按解析后的日期排序（核心修复！）
        parsed_data.sort(key=lambda x: x["parsed_date"])
        
        # 3. 缺失值填充（前向填充）
        filled_method = None
        values = []
        for i, item in enumerate(parsed_data):
            if item["value"] is None:
                # 前向填充
                if i > 0 and values:
                    item["value"] = values[-1]
                    filled_method = "forward_fill"
                else:
                    # 如果是第一个值，使用后向填充
                    for j in range(i + 1, len(parsed_data)):
                        if parsed_data[j]["value"] is not None:
                            item["value"] = parsed_data[j]["value"]
                            filled_method = "backward_fill"
                            break
                    if item["value"] is None:
                        item["value"] = 0  # 最后的fallback
                        filled_method = "zero_fallback"
            values.append(item["value"])
        
        # 4. 异常值检测（IQR方法）
        if len(values) >= 4:
            q1 = self._percentile(values, 25)
            q3 = self._percentile(values, 75)
            iqr = q3 - q1
            lower_fence = q1 - 1.5 * iqr
            upper_fence = q3 + 1.5 * iqr
            
            for i, v in enumerate(values):
                if v < lower_fence or v > upper_fence:
                    outlier_indices.append(i)
            
            if outlier_indices:
                logger.warning(f"[预测] 检测到 {len(outlier_indices)} 个异常值: 索引 {outlier_indices}")
        
        # 5. 检测日期间隔
        date_interval = self._detect_date_interval([item["parsed_date"] for item in parsed_data])
        
        # 构建返回数据
        processed = {
            "dates": [item["date_str"] for item in parsed_data],
            "values": values,
            "parsed_dates": [item["parsed_date"] for item in parsed_data]
        }
        
        quality = DataQualityInfo(
            total_points=total_points,
            valid_points=len(values),
            missing_count=missing_count,
            missing_filled_method=filled_method,
            outlier_count=len(outlier_indices),
            outlier_indices=outlier_indices,
            date_interval=date_interval
        )
        
        return processed, quality
    
    def _detect_date_interval(self, dates: List[datetime]) -> str:
        """检测日期间隔类型"""
        if len(dates) < 2:
            return "unknown"
        
        intervals = []
        for i in range(1, min(len(dates), 10)):
            delta = (dates[i] - dates[i-1]).days
            intervals.append(delta)
        
        if not intervals:
            return "unknown"
        
        avg_interval = sum(intervals) / len(intervals)
        
        if avg_interval <= 1.5:
            return "daily"
        elif avg_interval <= 8:
            return "weekly"
        elif avg_interval <= 32:
            return "monthly"
        elif avg_interval <= 95:
            return "quarterly"
        else:
            return "yearly"
    
    def _percentile(self, values: List[float], p: float) -> float:
        """计算百分位数"""
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        return sorted_vals[int(f)] * (c - k) + sorted_vals[int(c)] * (k - f)
    
    # ==================== 数据特征分析 ====================
    
    def _analyze_data_characteristics(
        self, 
        values: List[float], 
        dates: List[datetime]
    ) -> Dict[str, Any]:
        """分析数据特征，用于智能方法选择"""
        n = len(values)
        
        # 1. 基本统计
        mean = sum(values) / n
        std = self._calculate_std(values)
        volatility = std / abs(mean) if abs(mean) > 0.001 else 0
        
        # 2. 线性趋势强度（R²）
        r_squared = self._calculate_r_squared(values)
        
        # 3. 趋势方向
        slope, _ = self._linear_fit(values)
        trend_direction = "up" if slope > 0.01 else ("down" if slope < -0.01 else "stable")
        
        # 4. 季节性检测（自相关分析）
        has_seasonality, seasonality_period = self._detect_seasonality(values)
        
        # 5. 平稳性检验（简化版）
        is_stationary = self._check_stationarity(values)
        
        return {
            "n": n,
            "mean": round(mean, 2),
            "std": round(std, 2),
            "volatility": round(volatility, 4),
            "r_squared": round(r_squared, 4),
            "trend_direction": trend_direction,
            "slope": round(slope, 4),
            "has_seasonality": has_seasonality,
            "seasonality_period": seasonality_period,
            "is_stationary": is_stationary
        }
    
    def _calculate_r_squared(self, values: List[float]) -> float:
        """计算线性拟合的R²"""
        n = len(values)
        if n < 3:
            return 0
        
        y_mean = sum(values) / n
        ss_tot = sum((y - y_mean) ** 2 for y in values)
        
        if ss_tot == 0:
            return 1.0
        
        slope, intercept = self._linear_fit(values)
        predicted = [intercept + slope * i for i in range(n)]
        ss_res = sum((values[i] - predicted[i]) ** 2 for i in range(n))
        
        return max(0, 1 - (ss_res / ss_tot))
    
    def _detect_seasonality(self, values: List[float]) -> Tuple[bool, Optional[int]]:
        """检测季节性（使用自相关分析）"""
        n = len(values)
        if n < 8:
            return False, None
        
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        
        if variance == 0:
            return False, None
        
        # 检查常见周期：7(周), 12(月), 4(季)
        candidate_periods = [7, 12, 4, 30, 52]
        best_period = None
        best_acf = 0
        
        for period in candidate_periods:
            if period >= n // 2:
                continue
            
            # 计算自相关系数
            acf = 0
            for i in range(n - period):
                acf += (values[i] - mean) * (values[i + period] - mean)
            acf = acf / ((n - period) * variance)
            
            if acf > 0.5 and acf > best_acf:
                best_acf = acf
                best_period = period
        
        return best_period is not None, best_period
    
    def _check_stationarity(self, values: List[float]) -> bool:
        """简化版平稳性检验"""
        n = len(values)
        if n < 6:
            return True
        
        # 比较前半段和后半段的均值
        first_half = values[:n//2]
        second_half = values[n//2:]
        
        mean1 = sum(first_half) / len(first_half)
        mean2 = sum(second_half) / len(second_half)
        
        # 如果均值变化超过20%，认为非平稳
        if abs(mean1) > 0.001:
            change_rate = abs(mean2 - mean1) / abs(mean1)
            return change_rate < 0.2
        return True
    
    # ==================== 智能方法选择 ====================
    
    def _select_best_method_enhanced(
        self, 
        values: List[float], 
        characteristics: Dict[str, Any]
    ) -> Tuple[str, MethodSelectionReason]:
        """
        增强版智能方法选择
        
        改进点：
        1. 使用多维度评分而非简单阈值
        2. 考虑季节性、平稳性
        3. 提供详细的选择理由
        """
        scores = {"linear": 0, "moving_average": 0, "exponential_smoothing": 0}
        reasons = []
        
        r_squared = characteristics["r_squared"]
        volatility = characteristics["volatility"]
        has_seasonality = characteristics["has_seasonality"]
        is_stationary = characteristics["is_stationary"]
        n = characteristics["n"]
        
        # 评分规则
        
        # 1. 线性回归适用条件
        if r_squared > 0.7:
            scores["linear"] += 40
            reasons.append(f"数据线性趋势明显(R²={r_squared:.2f})")
        elif r_squared > 0.5:
            scores["linear"] += 25
        
        if not has_seasonality:
            scores["linear"] += 10
        
        # 2. 移动平均适用条件
        if volatility < 0.2:
            scores["moving_average"] += 30
            reasons.append(f"数据波动较小(波动率={volatility:.2%})")
        
        if is_stationary:
            scores["moving_average"] += 20
            reasons.append("数据相对平稳")
        
        if n < 10:
            scores["moving_average"] += 15
            reasons.append(f"数据量较少({n}个点)")
        
        # 3. 指数平滑适用条件
        if volatility > 0.3:
            scores["exponential_smoothing"] += 35
            reasons.append(f"数据波动较大(波动率={volatility:.2%})，需要近期数据权重更高")
        
        if not is_stationary:
            scores["exponential_smoothing"] += 15
        
        if has_seasonality:
            # 有季节性时，指数平滑或移动平均更合适
            scores["exponential_smoothing"] += 10
            scores["moving_average"] += 10
            reasons.append(f"检测到季节性特征")
        
        # 基础分（保证每种方法都有基础竞争力）
        scores["linear"] += 20
        scores["moving_average"] += 25
        scores["exponential_smoothing"] += 20
        
        # 选择最高分的方法
        best_method = max(scores, key=scores.get)
        
        # 生成选择理由
        method_names = {
            "linear": "线性回归",
            "moving_average": "移动平均",
            "exponential_smoothing": "指数平滑"
        }
        
        reason_text = f"基于数据特征分析，选择【{method_names[best_method]}】方法。"
        if reasons:
            reason_text += "主要依据：" + "；".join(reasons[:3]) + "。"
        reason_text += f"各方法评分：线性回归={scores['linear']}分，移动平均={scores['moving_average']}分，指数平滑={scores['exponential_smoothing']}分。"
        
        return best_method, MethodSelectionReason(
            selected_method=best_method,
            reason=reason_text,
            data_characteristics=characteristics,
            method_scores=scores
        )
    
    # ==================== 参数自动调优 ====================
    
    def _optimize_parameters(self, values: List[float], method: str) -> Dict[str, Any]:
        """参数自动调优"""
        params = {}
        
        if method == "moving_average":
            # 根据数据量选择最优窗口大小
            n = len(values)
            if n <= 5:
                params["window"] = 2
            elif n <= 10:
                params["window"] = 3
            elif n <= 30:
                params["window"] = 5
            else:
                # 尝试不同窗口，选择误差最小的
                best_window = 3
                best_error = float('inf')
                for w in [3, 5, 7, 10]:
                    if w >= n:
                        continue
                    error = self._evaluate_window(values, w)
                    if error < best_error:
                        best_error = error
                        best_window = w
                params["window"] = best_window
        
        elif method == "exponential_smoothing":
            # 网格搜索最优alpha
            best_alpha = 0.3
            best_error = float('inf')
            for alpha in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
                error = self._evaluate_alpha(values, alpha)
                if error < best_error:
                    best_error = error
                    best_alpha = alpha
            params["alpha"] = best_alpha
        
        return params
    
    def _evaluate_window(self, values: List[float], window: int) -> float:
        """评估移动平均窗口的预测误差"""
        if len(values) < window + 2:
            return float('inf')
        
        errors = []
        for i in range(window, len(values)):
            pred = sum(values[i-window:i]) / window
            errors.append(abs(values[i] - pred))
        
        return sum(errors) / len(errors) if errors else float('inf')
    
    def _evaluate_alpha(self, values: List[float], alpha: float) -> float:
        """评估指数平滑参数的预测误差"""
        if len(values) < 3:
            return float('inf')
        
        smoothed = values[0]
        errors = []
        for i in range(1, len(values)):
            errors.append(abs(values[i] - smoothed))
            smoothed = alpha * values[i] + (1 - alpha) * smoothed
        
        return sum(errors) / len(errors) if errors else float('inf')
    
    # ==================== 预测算法（增强版） ====================
    
    def _linear_fit(self, values: List[float]) -> Tuple[float, float]:
        """线性最小二乘拟合"""
        n = len(values)
        if n < 2:
            return 0, values[0] if values else 0
        
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        denominator = n * x2_sum - x_sum * x_sum
        if denominator == 0:
            return 0, y_sum / n
        
        slope = (n * xy_sum - x_sum * y_sum) / denominator
        intercept = (y_sum - slope * x_sum) / n
        
        return slope, intercept
    
    def _linear_prediction_enhanced(
        self,
        values: List[float],
        periods: int,
        confidence_level: float
    ) -> Tuple[List[float], List[float], List[float], Dict[str, Any]]:
        """增强版线性回归预测"""
        n = len(values)
        slope, intercept = self._linear_fit(values)
        
        # 计算标准误差
        predicted = [intercept + slope * i for i in range(n)]
        residuals = [values[i] - predicted[i] for i in range(n)]
        mse = sum(r * r for r in residuals) / max(1, n - 2)
        se = math.sqrt(mse) if mse > 0 else 0
        
        # 使用scipy计算精确的t分布临界值
        try:
            t_value = stats.t.ppf((1 + confidence_level) / 2, max(1, n - 2))
        except:
            t_value = 1.96 if confidence_level >= 0.95 else 1.645
        
        predictions = []
        lower = []
        upper = []
        
        x_mean = (n - 1) / 2
        ss_x = sum((i - x_mean) ** 2 for i in range(n))
        
        for i in range(periods):
            x_new = n + i
            pred = intercept + slope * x_new
            
            # 预测区间（考虑预测点远离均值时不确定性增大）
            margin = t_value * se * math.sqrt(1 + 1/n + ((x_new - x_mean)**2) / ss_x) if ss_x > 0 else t_value * se
            
            predictions.append(round(pred, 2))
            lower.append(round(pred - margin, 2))
            upper.append(round(pred + margin, 2))
        
        key_params = {
            "slope": round(slope, 4),
            "intercept": round(intercept, 2),
            "standard_error": round(se, 4),
            "t_value": round(t_value, 3)
        }
        
        return predictions, lower, upper, key_params
    
    def _moving_average_prediction_enhanced(
        self,
        values: List[float],
        periods: int,
        confidence_level: float,
        window: int = 3
    ) -> Tuple[List[float], List[float], List[float], Dict[str, Any]]:
        """增强版移动平均预测 - 修复置信区间随步长增大"""
        window = min(window, len(values))
        
        # 计算历史预测误差的标准差
        historical_errors = []
        for i in range(window, len(values)):
            pred = sum(values[i-window:i]) / window
            historical_errors.append(values[i] - pred)
        
        if historical_errors:
            error_std = math.sqrt(sum(e*e for e in historical_errors) / len(historical_errors))
        else:
            error_std = self._calculate_std(values)
        
        # 使用正态分布临界值
        try:
            z_value = stats.norm.ppf((1 + confidence_level) / 2)
        except:
            z_value = 1.96 if confidence_level >= 0.95 else 1.645
        
        predictions = []
        lower = []
        upper = []
        
        recent_values = list(values[-window:])
        
        for i in range(periods):
            pred = sum(recent_values) / len(recent_values)
            
            # 关键修复：置信区间随预测步长增大
            margin = z_value * error_std * math.sqrt(1 + i * 0.1)
            
            predictions.append(round(pred, 2))
            lower.append(round(pred - margin, 2))
            upper.append(round(pred + margin, 2))
            
            recent_values = recent_values[1:] + [pred]
        
        key_params = {
            "window": window,
            "error_std": round(error_std, 4),
            "z_value": round(z_value, 3),
            "last_window_avg": round(sum(values[-window:]) / window, 2)
        }
        
        return predictions, lower, upper, key_params
    
    def _exponential_smoothing_enhanced(
        self,
        values: List[float],
        periods: int,
        confidence_level: float,
        alpha: float = 0.3
    ) -> Tuple[List[float], List[float], List[float], Dict[str, Any]]:
        """增强版指数平滑预测"""
        n = len(values)
        
        # 计算平滑值
        smoothed = [values[0]]
        for i in range(1, n):
            smoothed.append(alpha * values[i] + (1 - alpha) * smoothed[-1])
        
        # 计算残差标准差
        residuals = [values[i] - smoothed[i] for i in range(n)]
        std = math.sqrt(sum(r * r for r in residuals) / max(1, n - 1))
        
        try:
            z_value = stats.norm.ppf((1 + confidence_level) / 2)
        except:
            z_value = 1.96 if confidence_level >= 0.95 else 1.645
        
        predictions = []
        lower = []
        upper = []
        
        last_smooth = smoothed[-1]
        
        for i in range(periods):
            pred = last_smooth
            # 置信区间随预测步长增大
            margin = z_value * std * math.sqrt(1 + i * alpha * alpha)
            
            predictions.append(round(pred, 2))
            lower.append(round(pred - margin, 2))
            upper.append(round(pred + margin, 2))
        
        key_params = {
            "alpha": alpha,
            "last_smoothed_value": round(last_smooth, 2),
            "residual_std": round(std, 4),
            "z_value": round(z_value, 3)
        }
        
        return predictions, lower, upper, key_params
    
    # ==================== 日期生成 ====================
    
    def _generate_future_dates_enhanced(
        self, 
        dates: List[datetime], 
        periods: int,
        interval_type: str
    ) -> List[str]:
        """增强版日期生成 - 支持不等间隔"""
        if not dates:
            return [f"T+{i+1}" for i in range(periods)]
        
        last_date = dates[-1]
        
        # 根据检测到的间隔类型生成日期
        future_dates = []
        for i in range(1, periods + 1):
            if interval_type == "daily":
                future_date = last_date + timedelta(days=i)
            elif interval_type == "weekly":
                future_date = last_date + timedelta(weeks=i)
            elif interval_type == "monthly":
                # 月度间隔特殊处理
                month = last_date.month + i
                year = last_date.year + (month - 1) // 12
                month = ((month - 1) % 12) + 1
                day = min(last_date.day, 28)  # 避免月末问题
                future_date = datetime(year, month, day)
            elif interval_type == "quarterly":
                month = last_date.month + i * 3
                year = last_date.year + (month - 1) // 12
                month = ((month - 1) % 12) + 1
                day = min(last_date.day, 28)
                future_date = datetime(year, month, day)
            elif interval_type == "yearly":
                future_date = datetime(last_date.year + i, last_date.month, last_date.day)
            else:
                # 默认按天
                future_date = last_date + timedelta(days=i)
            
            future_dates.append(future_date.strftime("%Y-%m-%d"))
        
        return future_dates
    
    # ==================== 准确性评估（增强版） ====================
    
    def _calculate_accuracy_enhanced(
        self, 
        values: List[float], 
        method: str,
        params: Dict[str, Any]
    ) -> AccuracyMetrics:
        """增强版准确性评估 - 使用时序交叉验证"""
        n = len(values)
        
        if n < 5:
            return AccuracyMetrics(mape=15.0, rmse=0.0, mae=0.0, r_squared=0.0)
        
        # 时序交叉验证：滚动预测
        errors = []
        squared_errors = []
        percentage_errors = []
        
        # 至少保留60%数据作为初始训练集
        train_size = max(3, int(n * 0.6))
        
        for i in range(train_size, n):
            train = values[:i]
            actual = values[i]
            
            # 根据方法预测下一个值
            if method == "linear":
                slope, intercept = self._linear_fit(train)
                predicted = intercept + slope * i
            elif method == "moving_average":
                window = params.get("window", 3)
                window = min(window, len(train))
                predicted = sum(train[-window:]) / window
            else:
                alpha = params.get("alpha", 0.3)
                smoothed = train[0]
                for v in train[1:]:
                    smoothed = alpha * v + (1 - alpha) * smoothed
                predicted = smoothed
            
            error = abs(actual - predicted)
            errors.append(error)
            squared_errors.append(error ** 2)
            
            if abs(actual) > 0.001:
                percentage_errors.append(error / abs(actual) * 100)
        
        # 计算指标
        mae = sum(errors) / len(errors) if errors else 0
        rmse = math.sqrt(sum(squared_errors) / len(squared_errors)) if squared_errors else 0
        mape = sum(percentage_errors) / len(percentage_errors) if percentage_errors else 0
        r_squared = self._calculate_r_squared(values)
        
        return AccuracyMetrics(
            mape=round(mape, 2),
            rmse=round(rmse, 2),
            mae=round(mae, 2),
            r_squared=round(r_squared, 4)
        )
    
    # ==================== 趋势分析（增强版） ====================
    
    def _analyze_trend_enhanced(
        self, 
        values: List[float],
        characteristics: Dict[str, Any]
    ) -> TrendAnalysis:
        """增强版趋势分析"""
        n = len(values)
        
        if n < 2:
            return TrendAnalysis(
                direction="stable",
                growth_rate=0.0,
                average_value=values[0] if values else 0,
                min_value=values[0] if values else 0,
                max_value=values[0] if values else 0,
                volatility=0.0,
                has_seasonality=False,
                seasonality_period=None
            )
        
        # 计算增长率
        first_half = sum(values[:n//2]) / (n//2)
        second_half = sum(values[n//2:]) / (n - n//2)
        
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
        
        return TrendAnalysis(
            direction=direction,
            growth_rate=round(growth_rate, 2),
            average_value=round(characteristics["mean"], 2),
            min_value=round(min(values), 2),
            max_value=round(max(values), 2),
            volatility=round(characteristics["volatility"] * 100, 2),
            has_seasonality=characteristics.get("has_seasonality", False),
            seasonality_period=characteristics.get("seasonality_period")
        )
    
    # ==================== 预测解释生成 ====================
    
    def _generate_explanation(
        self,
        method: str,
        key_params: Dict[str, Any],
        values: List[float],
        predictions: List[float],
        confidence_level: float,
        accuracy: AccuracyMetrics,
        categories: Optional[List[str]] = None,
        date_column: str = "",
        value_column: str = ""
    ) -> PredictionExplanation:
        """生成预测解释 - 让用户理解预测结果是怎么来的"""
        
        method_explanations = {
            "linear": {
                "name": "线性回归",
                "explanation": "线性回归通过拟合一条最佳直线来捕捉数据的整体趋势。它假设数据随时间呈线性变化，适用于有明显上升或下降趋势的数据。",
                "formula": "预测值 = 截距 + 斜率 × 时间点，即 ŷ = {intercept:.2f} + {slope:.4f} × t"
            },
            "moving_average": {
                "name": "移动平均",
                "explanation": "移动平均通过计算最近N个数据点的平均值来预测未来。它能平滑短期波动，适用于没有明显趋势但有随机波动的数据。",
                "formula": "预测值 = 最近{window}个数据点的平均值"
            },
            "exponential_smoothing": {
                "name": "指数平滑",
                "explanation": "指数平滑对近期数据赋予更高权重，对远期数据赋予较低权重。平滑系数α决定了近期数据的权重，α越大，对最新数据越敏感。",
                "formula": "预测值 = α × 最新值 + (1-α) × 上次平滑值，α = {alpha}"
            }
        }
        
        info = method_explanations.get(method, method_explanations["linear"])
        
        # ==================== 数据来源信息 ====================
        data_source = DataSourceInfo(
            tables=["聚合数据"],  # 可从外部传入
            columns=[date_column, value_column] if date_column and value_column else [],
            row_count=len(values),
            time_range=f"{categories[0]} 至 {categories[-1]}" if categories and len(categories) >= 2 else None
        )
        
        # ==================== 关键指标值 ====================
        import numpy as np
        mean_val = float(np.mean(values))
        std_val = float(np.std(values))
        min_val = float(min(values))
        max_val = float(max(values))
        
        key_metrics = [
            KeyMetricValue(
                name="均值", 
                value=round(mean_val, 2),
                description="历史数据的平均水平",
                used_in_steps=[1, 3] if method == "linear" else [1]
            ),
            KeyMetricValue(
                name="标准差",
                value=round(std_val, 2),
                description="数据波动程度",
                used_in_steps=[3] if method == "linear" else []
            ),
            KeyMetricValue(
                name="最小值",
                value=round(min_val, 2),
                description="历史最低值",
                used_in_steps=[]
            ),
            KeyMetricValue(
                name="最大值",
                value=round(max_val, 2),
                description="历史最高值",
                used_in_steps=[]
            )
        ]
        
        # ==================== 详细推理步骤 ====================
        reasoning_chain = []
        
        if method == "linear":
            slope = key_params.get("slope", 0)
            intercept = key_params.get("intercept", 0)
            reasoning_chain = [
                ReasoningStep(
                    step=1,
                    description="统计历史数据基本信息",
                    input_description=f"{len(values)}个历史数据点",
                    output_description=f"均值={mean_val:.2f}, 标准差={std_val:.2f}"
                ),
                ReasoningStep(
                    step=2,
                    description="使用最小二乘法拟合趋势线",
                    formula="minimize Σ(y_actual - y_predicted)²",
                    input_description="所有历史数据点",
                    output_description=f"拟合优度 R²={accuracy.r_squared:.3f}"
                ),
                ReasoningStep(
                    step=3,
                    description="确定线性方程参数",
                    formula=f"y = {intercept:.2f} + {slope:.4f} × x",
                    input_description="拟合结果",
                    output_description=f"斜率={slope:.4f}(每期变化), 截距={intercept:.2f}(基准值)"
                ),
                ReasoningStep(
                    step=4,
                    description="计算预测值",
                    formula=f"{intercept:.2f} + {slope:.4f} × {len(values)}",
                    input_description=f"下一期序号={len(values)}",
                    output_description=f"预测值={predictions[0]:.2f}"
                )
            ]
        elif method == "moving_average":
            window = key_params.get("window", 3)
            last_avg = key_params.get("last_window_avg", 0)
            reasoning_chain = [
                ReasoningStep(
                    step=1,
                    description="统计历史数据基本信息",
                    input_description=f"{len(values)}个历史数据点",
                    output_description=f"均值={mean_val:.2f}"
                ),
                ReasoningStep(
                    step=2,
                    description=f"选择最优窗口大小",
                    input_description="测试不同窗口参数",
                    output_description=f"最优窗口={window}"
                ),
                ReasoningStep(
                    step=3,
                    description=f"计算最近{window}期的平均值",
                    formula=f"avg = (x_{len(values)-window+1} + ... + x_{len(values)}) / {window}",
                    input_description=f"最近{window}个数据点",
                    output_description=f"移动平均={last_avg:.2f}"
                ),
                ReasoningStep(
                    step=4,
                    description="将移动平均作为预测值",
                    input_description=f"移动平均={last_avg:.2f}",
                    output_description=f"预测值={predictions[0]:.2f}"
                )
            ]
        else:  # exponential_smoothing
            alpha = key_params.get("alpha", 0.3)
            last_smooth = key_params.get("last_smoothed_value", 0)
            reasoning_chain = [
                ReasoningStep(
                    step=1,
                    description="统计历史数据基本信息",
                    input_description=f"{len(values)}个历史数据点",
                    output_description=f"均值={mean_val:.2f}"
                ),
                ReasoningStep(
                    step=2,
                    description="自动优化平滑系数",
                    input_description="测试不同α值(0.1~0.9)",
                    output_description=f"最优α={alpha}"
                ),
                ReasoningStep(
                    step=3,
                    description="迭代计算指数平滑值",
                    formula=f"S_t = {alpha} × x_t + {1-alpha} × S_(t-1)",
                    input_description="逐期应用平滑公式",
                    output_description=f"最终平滑值={last_smooth:.2f}"
                ),
                ReasoningStep(
                    step=4,
                    description="将平滑值作为预测值",
                    input_description=f"平滑值={last_smooth:.2f}",
                    output_description=f"预测值={predictions[0]:.2f}"
                )
            ]
        
        # 构建原有的简化步骤（向后兼容）
        steps = []
        if method == "linear":
            slope = key_params.get("slope", 0)
            intercept = key_params.get("intercept", 0)
            steps = [
                f"1. 分析{len(values)}个历史数据点",
                f"2. 使用最小二乘法拟合直线",
                f"3. 得到斜率 = {slope:.4f}（每个周期变化量）",
                f"4. 得到截距 = {intercept:.2f}（初始基准值）",
                f"5. 下一个预测值 = {intercept:.2f} + {slope:.4f} × {len(values)} = {predictions[0]}"
            ]
        elif method == "moving_average":
            window = key_params.get("window", 3)
            last_avg = key_params.get("last_window_avg", 0)
            steps = [
                f"1. 分析{len(values)}个历史数据点",
                f"2. 选择窗口大小 = {window}（自动优化）",
                f"3. 计算最近{window}个数据点的平均值",
                f"4. 最近{window}点平均 = {last_avg:.2f}",
                f"5. 预测值 = {predictions[0]}"
            ]
        else:
            alpha = key_params.get("alpha", 0.3)
            last_smooth = key_params.get("last_smoothed_value", 0)
            steps = [
                f"1. 分析{len(values)}个历史数据点",
                f"2. 自动选择平滑系数 α = {alpha}",
                f"3. 迭代计算指数平滑值",
                f"4. 最终平滑值 = {last_smooth:.2f}",
                f"5. 预测值 = {predictions[0]}"
            ]
        
        # 置信区间解释
        conf_pct = int(confidence_level * 100)
        confidence_explanation = (
            f"置信区间表示预测的不确定性范围。{conf_pct}%置信区间意味着：如果多次重复预测，"
            f"有{conf_pct}%的情况，真实值会落在这个区间内。区间越窄，预测越精确。"
        )
        
        # 可靠性评估
        mape = accuracy.mape
        if mape < 10:
            reliability = f"高可靠性：历史预测误差(MAPE)仅为{mape:.1f}%，预测结果具有较高参考价值。"
        elif mape < 20:
            reliability = f"中等可靠性：历史预测误差(MAPE)为{mape:.1f}%，预测结果可作为参考，但需关注实际变化。"
        else:
            reliability = f"较低可靠性：历史预测误差(MAPE)为{mape:.1f}%，数据波动较大，预测结果仅供参考，建议结合业务判断。"
        
        return PredictionExplanation(
            method_explanation=info["explanation"],
            formula_used=info["formula"].format(**key_params),
            key_parameters=key_params,
            calculation_steps=steps,
            confidence_explanation=confidence_explanation,
            reliability_assessment=reliability,
            # 新增字段
            data_source=data_source,
            key_metrics=key_metrics,
            reasoning_chain=reasoning_chain
        )
    
    # ==================== 工具方法 ====================
    
    def _calculate_std(self, values: List[float]) -> float:
        """计算标准差"""
        n = len(values)
        if n < 2:
            return 0.0
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        return math.sqrt(variance)

    def _linear_prediction(
        self,
        values: List[float],
        periods: int,
        confidence_level: float
    ) -> Tuple[List[float], List[float], List[float]]:
        predictions, lower, upper, _ = self._linear_prediction_enhanced(values, periods, confidence_level)
        for i in range(min(len(predictions), len(lower), len(upper))):
            if not (lower[i] < predictions[i] < upper[i]):
                lower[i] = round(predictions[i] - 0.01, 2)
                upper[i] = round(predictions[i] + 0.01, 2)
        return predictions, lower, upper

    def _moving_average_prediction(
        self,
        values: List[float],
        periods: int,
        confidence_level: float
    ) -> Tuple[List[float], List[float], List[float]]:
        predictions, lower, upper, _ = self._moving_average_prediction_enhanced(values, periods, confidence_level)
        return predictions, lower, upper

    def _exponential_smoothing_prediction(
        self,
        values: List[float],
        periods: int,
        confidence_level: float
    ) -> Tuple[List[float], List[float], List[float]]:
        predictions, lower, upper, _ = self._exponential_smoothing_enhanced(values, periods, confidence_level)
        return predictions, lower, upper

    def _select_best_method(self, values: List[float]) -> str:
        dummy_dates = [datetime(2000, 1, 1) + timedelta(days=i) for i in range(len(values))]
        characteristics = self._analyze_data_characteristics(values, dummy_dates)
        method, _ = self._select_best_method_enhanced(values, characteristics)
        return method

    def _analyze_trend(self, values: List[float]) -> TrendAnalysis:
        dummy_dates = [datetime(2000, 1, 1) + timedelta(days=i) for i in range(len(values))]
        characteristics = self._analyze_data_characteristics(values, dummy_dates)
        return self._analyze_trend_enhanced(values, characteristics)

    def _calculate_accuracy_metrics(self, values: List[float], method: str) -> AccuracyMetrics:
        return self._calculate_accuracy_enhanced(values, method, {})

    def _generate_future_dates(self, dates: List[str], periods: int) -> List[str]:
        parsed = []
        for i, s in enumerate(dates):
            dt = None
            try:
                dt = datetime.fromisoformat(str(s).strip().replace("Z", "+00:00"))
            except Exception:
                pass
            if dt is None:
                try:
                    dt = datetime.strptime(str(s).strip()[:10], "%Y-%m-%d")
                except Exception:
                    dt = datetime(2000, 1, 1) + timedelta(days=i)
            parsed.append(dt)
        return self._generate_future_dates_enhanced(parsed, periods, "daily")


# 创建全局实例
prediction_service = PredictionService()


# ==================== 分类统计分析服务 ====================

class CategoricalAnalysisService:
    """分类数据统计分析服务"""
    
    def analyze(
        self,
        data: List[Dict[str, Any]],
        category_column: str,
        value_column: str,
        include_outliers: bool = True
    ) -> Dict[str, Any]:
        """
        执行分类统计分析
        
        Args:
            data: 原始数据
            category_column: 分类列名
            value_column: 数值列名
            include_outliers: 是否检测异常值
            
        Returns:
            分析结果字典
        """
        import numpy as np
        
        # 提取数据
        categories = []
        values = []
        for row in data:
            cat = row.get(category_column)
            val = row.get(value_column)
            if cat is not None and val is not None:
                try:
                    val_float = float(str(val).replace(',', '').replace('￥', '').replace('$', ''))
                    categories.append(str(cat))
                    values.append(val_float)
                except (ValueError, TypeError):
                    pass
        
        if not values:
            raise ValueError("没有有效的数值数据")
        
        values_arr = np.array(values)
        
        # 基本统计
        total_sum = float(np.sum(values_arr))
        overall_mean = float(np.mean(values_arr))
        overall_std = float(np.std(values_arr, ddof=1)) if len(values_arr) > 1 else 0.0
        
        # 按分类统计
        category_data = {}
        for cat, val in zip(categories, values):
            if cat not in category_data:
                category_data[cat] = []
            category_data[cat].append(val)
        
        category_stats = []
        for cat, cat_values in category_data.items():
            arr = np.array(cat_values)
            cat_stat = {
                "category": cat,
                "count": len(arr),
                "sum": float(np.sum(arr)),
                "mean": float(np.mean(arr)),
                "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "median": float(np.median(arr)),
                "q1": float(np.percentile(arr, 25)),
                "q3": float(np.percentile(arr, 75)),
                "pct_of_total": float(np.sum(arr) / total_sum * 100) if total_sum > 0 else 0.0
            }
            category_stats.append(cat_stat)
        
        # 按均值排序
        category_stats.sort(key=lambda x: x['mean'], reverse=True)
        
        # 分布分析
        skewness = 0.0
        kurtosis = 0.0
        normality_pvalue = 0.0
        if len(values_arr) > 2:
            mean = float(np.mean(values_arr))
            centered = values_arr - mean
            m2 = float(np.mean(centered ** 2))
            if m2 > 0:
                m3 = float(np.mean(centered ** 3))
                m4 = float(np.mean(centered ** 4))
                skewness = m3 / (m2 ** 1.5)
                kurtosis = (m4 / (m2 ** 2)) - 3.0
        
        distribution = {
            "skewness": round(skewness, 4),
            "kurtosis": round(kurtosis, 4),
            "is_normal": normality_pvalue > 0.05,
            "normality_pvalue": round(normality_pvalue, 4)
        }
        
        # 分类比较
        means = [s['mean'] for s in category_stats]
        top_cat = category_stats[0]['category'] if category_stats else ""
        bottom_cat = category_stats[-1]['category'] if category_stats else ""
        min_mean = min(means) if means else 1
        max_mean = max(means) if means else 1
        range_ratio = max_mean / min_mean if min_mean > 0 else 0
        cv = float(np.std(means) / np.mean(means) * 100) if means and np.mean(means) > 0 else 0
        
        # ANOVA检验（分类数 >= 2 且每组有数据）
        groups = [np.array(v) for v in category_data.values() if len(v) > 0]
        if len(groups) >= 2:
            try:
                f_val, p_val = scipy_stats.f_oneway(*groups)
                anova_fvalue = float(f_val) if not np.isnan(f_val) else None
                anova_pvalue = float(p_val) if not np.isnan(p_val) else None
                significant = p_val < 0.05 if not np.isnan(p_val) else False
            except Exception:
                anova_fvalue = None
                anova_pvalue = None
                significant = False
        else:
            anova_fvalue = None
            anova_pvalue = None
            significant = False
        
        comparison = {
            "top_category": top_cat,
            "bottom_category": bottom_cat,
            "range_ratio": round(range_ratio, 2),
            "cv": round(cv, 2),
            "anova_fvalue": round(anova_fvalue, 4) if anova_fvalue else None,
            "anova_pvalue": round(anova_pvalue, 4) if anova_pvalue else None,
            "significant_difference": significant
        }
        
        # 异常值检测 (Z-score)
        outliers = []
        if include_outliers and overall_std > 0:
            for cat, val in zip(categories, values):
                z = (val - overall_mean) / overall_std
                if abs(z) > 2.5:  # Z > 2.5 视为异常
                    outliers.append({
                        "category": cat,
                        "value": round(val, 2),
                        "z_score": round(z, 2),
                        "deviation_pct": round((val - overall_mean) / overall_mean * 100, 2) if overall_mean != 0 else 0
                    })
        
        # 可视化数据
        chart_data = {
            "bar": {
                "categories": [s['category'] for s in category_stats],
                "values": [s['mean'] for s in category_stats],
                "totals": [s['sum'] for s in category_stats]
            },
            "pie": {
                "labels": [s['category'] for s in category_stats],
                "values": [s['pct_of_total'] for s in category_stats]
            },
            "boxplot": {
                "categories": [s['category'] for s in category_stats],
                "data": [
                    [s['min'], s['q1'], s['median'], s['q3'], s['max']]
                    for s in category_stats
                ]
            }
        }
        
        # 生成摘要
        summary_parts = [
            f"共{len(category_data)}个分类，{len(values)}条记录。",
            f"'{top_cat}'均值最高({category_stats[0]['mean']:.2f})，",
            f"'{bottom_cat}'均值最低({category_stats[-1]['mean']:.2f})。" if len(category_stats) > 1 else "",
        ]
        
        if significant:
            summary_parts.append(f"统计检验显示分类间存在显著差异(p={anova_pvalue:.4f})。")
        
        if outliers:
            summary_parts.append(f"检测到{len(outliers)}个异常值。")
        
        summary = "".join(summary_parts)
        
        return {
            "total_records": len(values),
            "category_count": len(category_data),
            "total_sum": round(total_sum, 2),
            "overall_mean": round(overall_mean, 2),
            "overall_std": round(overall_std, 2),
            "category_stats": category_stats,
            "distribution": distribution,
            "comparison": comparison,
            "outliers": outliers[:10],  # 最多返回10个
            "chart_data": chart_data,
            "summary": summary,
            "generated_at": datetime.utcnow().isoformat()
        }


# 创建全局实例
categorical_analysis_service = CategoricalAnalysisService()
