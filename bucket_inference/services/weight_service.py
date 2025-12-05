"""가중치 계산 서비스 (버킷 추론용)"""

from typing import List, Dict, Tuple
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.models import BodyPartInput
from bucket_inference.models import BucketScore
from bucket_inference.config import settings


class WeightService:
    """가중치 기반 버킷 점수 계산"""

    def __init__(self):
        self._weights_cache = {}
        self._bucket_cache = {}

    def _load_weights(self, body_part: str) -> Tuple[Dict, List[str]]:
        """가중치 데이터 로드"""
        if body_part in self._weights_cache:
            return self._weights_cache[body_part], self._bucket_cache[body_part]

        weights_path = settings.data_dir / "clinical" / body_part / "weights.json"
        buckets_path = settings.data_dir / "clinical" / body_part / "buckets.json"

        if not weights_path.exists():
            raise FileNotFoundError(f"가중치 파일을 찾을 수 없습니다: {weights_path}")

        with open(weights_path, "r", encoding="utf-8") as f:
            weights_data = json.load(f)

        with open(buckets_path, "r", encoding="utf-8") as f:
            buckets_data = json.load(f)

        bucket_order = buckets_data.get("order", ["OA", "OVR", "TRM", "INF"])

        self._weights_cache[body_part] = weights_data
        self._bucket_cache[body_part] = bucket_order

        return weights_data, bucket_order

    def calculate_scores(
        self,
        body_part: BodyPartInput,
    ) -> Tuple[List[BucketScore], List[str]]:
        """
        증상 코드 기반 버킷 점수 계산

        Args:
            body_part: 부위별 입력 (증상 코드 포함)

        Returns:
            (버킷 점수 리스트, 순위 리스트)
        """
        weights, bucket_order = self._load_weights(body_part.code)

        # 버킷별 점수 초기화
        scores = {bucket: 0.0 for bucket in bucket_order}
        contributing = {bucket: [] for bucket in bucket_order}

        # 각 증상의 가중치 합산
        for symptom in body_part.symptoms:
            if symptom not in weights:
                continue

            weight_vector = weights[symptom]
            for i, bucket in enumerate(bucket_order):
                if i < len(weight_vector) and weight_vector[i] > 0:
                    scores[bucket] += weight_vector[i]
                    contributing[bucket].append(symptom)

        # 총점 계산
        total = sum(scores.values())
        if total == 0:
            total = 1  # 0 나눗셈 방지

        # BucketScore 리스트 생성
        bucket_scores = []
        for bucket in bucket_order:
            bucket_scores.append(
                BucketScore(
                    bucket=bucket,
                    score=round(scores[bucket], 2),
                    percentage=round((scores[bucket] / total) * 100, 1),
                    contributing_symptoms=list(set(contributing[bucket])),
                )
            )

        # 점수 순으로 정렬
        bucket_scores.sort(key=lambda x: x.score, reverse=True)

        # 순위 리스트
        ranking = [bs.bucket for bs in bucket_scores]

        return bucket_scores, ranking

    def get_score_dict(
        self,
        body_part: BodyPartInput,
    ) -> Dict[str, float]:
        """버킷별 점수 딕셔너리 반환"""
        bucket_scores, _ = self.calculate_scores(body_part)
        return {bs.bucket: bs.score for bs in bucket_scores}
