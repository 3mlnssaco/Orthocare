"""랭킹 통합 서비스

가중치 랭킹과 검색 랭킹을 Reciprocal Rank Fusion (RRF)으로 통합
"""

from typing import List, Dict

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bucket_inference.config import settings


class RankingMerger:
    """가중치/검색 랭킹 통합"""

    def __init__(self, weight_ratio: float = None):
        """
        Args:
            weight_ratio: 가중치 비율 (기본값: 설정에서 로드)
        """
        self.weight_ratio = weight_ratio or settings.weight_ratio

    def merge(
        self,
        weight_ranking: List[str],
        search_ranking: List[str],
    ) -> List[str]:
        """
        두 랭킹 병합 (Reciprocal Rank Fusion 변형)

        Args:
            weight_ranking: 가중치 기반 순위
            search_ranking: 검색 기반 순위

        Returns:
            통합된 버킷 순위
        """
        if not search_ranking:
            return weight_ranking

        scores: Dict[str, float] = {}

        # 가중치 랭킹 점수
        for i, bucket in enumerate(weight_ranking):
            rank_score = 1.0 / (i + 1)  # 순위 역수
            scores[bucket] = scores.get(bucket, 0) + rank_score * self.weight_ratio

        # 검색 랭킹 점수
        for i, bucket in enumerate(search_ranking):
            rank_score = 1.0 / (i + 1)
            scores[bucket] = scores.get(bucket, 0) + rank_score * (1 - self.weight_ratio)

        # 점수순 정렬
        sorted_buckets = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return sorted_buckets

    def get_merge_scores(
        self,
        weight_ranking: List[str],
        search_ranking: List[str],
    ) -> Dict[str, Dict[str, float]]:
        """
        병합 점수 상세 반환

        Returns:
            {버킷: {"weight_score": float, "search_score": float, "total": float}}
        """
        scores: Dict[str, Dict[str, float]] = {}

        # 가중치 랭킹 점수
        for i, bucket in enumerate(weight_ranking):
            rank_score = 1.0 / (i + 1) * self.weight_ratio
            scores[bucket] = {"weight_score": rank_score, "search_score": 0.0}

        # 검색 랭킹 점수
        for i, bucket in enumerate(search_ranking):
            rank_score = 1.0 / (i + 1) * (1 - self.weight_ratio)
            if bucket not in scores:
                scores[bucket] = {"weight_score": 0.0, "search_score": 0.0}
            scores[bucket]["search_score"] = rank_score

        # 총점 계산
        for bucket in scores:
            scores[bucket]["total"] = (
                scores[bucket]["weight_score"] + scores[bucket]["search_score"]
            )

        return scores
