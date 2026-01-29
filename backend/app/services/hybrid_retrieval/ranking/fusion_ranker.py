"""
多维度融合排序器
"""

import logging
from typing import List

from app.core.config import settings
from ..models import QAPairWithContext, RetrievalResult

logger = logging.getLogger(__name__)


class FusionRanker:
    """多维度融合排序器"""

    def __init__(self):
        self.weights = {
            'semantic': settings.SEMANTIC_WEIGHT,
            'structural': settings.STRUCTURAL_WEIGHT,
            'pattern': settings.PATTERN_WEIGHT,
            'quality': settings.QUALITY_WEIGHT
        }

    def fuse_and_rank(self, semantic_results: List[RetrievalResult],
                     structural_results: List[RetrievalResult],
                     pattern_results: List[RetrievalResult]) -> List[RetrievalResult]:
        """融合多个检索结果并排序"""

        # 1. 收集所有唯一的QA对
        all_qa_pairs = {}

        # 处理语义检索结果
        for result in semantic_results:
            qa_id = result.qa_pair.id
            if qa_id not in all_qa_pairs:
                all_qa_pairs[qa_id] = result
            else:
                all_qa_pairs[qa_id].semantic_score = max(
                    all_qa_pairs[qa_id].semantic_score, result.semantic_score
                )

        # 处理结构检索结果
        for result in structural_results:
            qa_id = result.qa_pair.id
            if qa_id not in all_qa_pairs:
                all_qa_pairs[qa_id] = result
            else:
                all_qa_pairs[qa_id].structural_score = max(
                    all_qa_pairs[qa_id].structural_score, result.structural_score
                )

        # 处理模式检索结果
        for result in pattern_results:
            qa_id = result.qa_pair.id
            if qa_id not in all_qa_pairs:
                all_qa_pairs[qa_id] = result
            else:
                all_qa_pairs[qa_id].pattern_score = max(
                    all_qa_pairs[qa_id].pattern_score, result.pattern_score
                )

        # 2. 计算质量分数和最终分数
        final_results = []
        for qa_id, result in all_qa_pairs.items():
            # 计算质量分数
            quality_score = self._calculate_quality_score(result.qa_pair)
            result.quality_score = quality_score

            # 计算最终分数 - 使用动态权重调整
            final_score = self._calculate_dynamic_final_score(
                result.semantic_score,
                result.structural_score,
                result.pattern_score,
                quality_score
            )
            result.final_score = final_score

            # 生成解释
            result.explanation = self._generate_explanation(result)

            final_results.append(result)

        # 3. 按最终分数排序
        return sorted(final_results, key=lambda x: x.final_score, reverse=True)

    def _calculate_quality_score(self, qa_pair: QAPairWithContext) -> float:
        """计算问答对的质量分数"""
        quality_score = 0.0

        # 验证状态加分
        if qa_pair.verified:
            quality_score += 0.3

        # 成功率加分
        quality_score += qa_pair.success_rate * 0.5

        # 难度适中加分（难度2-3的问答对通常质量较高）
        if 2 <= qa_pair.difficulty_level <= 3:
            quality_score += 0.2

        return min(1.0, quality_score)

    def _calculate_dynamic_final_score(self, semantic_score: float, structural_score: float,
                                     pattern_score: float, quality_score: float) -> float:
        """
        动态权重计算最终分数
        当语义相似度很高时，增加其权重；当语义相似度较低时，更多依赖结构和模式匹配
        """
        # 基础权重
        base_weights = {
            'semantic': self.weights['semantic'],
            'structural': self.weights['structural'],
            'pattern': self.weights['pattern'],
            'quality': self.weights['quality']
        }

        # 动态调整权重
        if semantic_score >= 0.9:
            # 语义高度匹配时，大幅提升语义权重
            adjusted_weights = {
                'semantic': 0.80,
                'structural': 0.10,
                'pattern': 0.05,
                'quality': 0.05
            }
        elif semantic_score >= 0.7:
            # 语义较好匹配时，适度提升语义权重
            adjusted_weights = {
                'semantic': 0.70,
                'structural': 0.15,
                'pattern': 0.10,
                'quality': 0.05
            }
        elif semantic_score >= 0.5:
            # 语义中等匹配时，使用调整后的基础权重
            adjusted_weights = base_weights
        else:
            # 语义匹配较差时，更多依赖结构和模式
            adjusted_weights = {
                'semantic': 0.40,
                'structural': 0.35,
                'pattern': 0.20,
                'quality': 0.05
            }

        # 计算最终分数
        final_score = (
            semantic_score * adjusted_weights['semantic'] +
            structural_score * adjusted_weights['structural'] +
            pattern_score * adjusted_weights['pattern'] +
            quality_score * adjusted_weights['quality']
        )

        return final_score

    def _generate_explanation(self, result: RetrievalResult) -> str:
        """生成推荐解释"""
        explanations = []

        # 语义相似度解释
        if result.semantic_score >= 0.9:
            explanations.append(f"语义高度相似({result.semantic_score:.2f})")
        elif result.semantic_score >= 0.7:
            explanations.append(f"语义相似({result.semantic_score:.2f})")
        elif result.semantic_score >= 0.5:
            explanations.append(f"语义部分相似({result.semantic_score:.2f})")

        # 结构相似度解释
        if result.structural_score > 0.7:
            explanations.append("使用相同的表结构")
        elif result.structural_score > 0.3:
            explanations.append("使用部分相同的表")

        # 模式匹配解释
        if result.pattern_score > 0.5:
            explanations.append("匹配相似的查询模式")

        # 质量指标解释
        if result.qa_pair.verified:
            explanations.append("已验证的高质量示例")

        # 动态权重提示
        if result.semantic_score >= 0.9:
            explanations.append("(语义优先权重)")
        elif result.semantic_score < 0.5:
            explanations.append("(结构模式优先权重)")

        return "; ".join(explanations) if explanations else "相关示例"
