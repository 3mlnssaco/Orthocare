"""버킷 추론 파이프라인

전체 흐름:
1. 가중치 계산
2. 벡터 검색
3. 랭킹 통합
4. LLM 버킷 중재
"""

from typing import Dict, List

from langsmith import traceable

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bucket_inference.models import BucketInferenceInput, BucketInferenceOutput
from bucket_inference.services import (
    WeightService,
    EvidenceSearchService,
    RankingMerger,
    BucketArbitrator,
)
from bucket_inference.config import settings


class BucketInferencePipeline:
    """버킷 추론 파이프라인

    사용 예시:
        pipeline = BucketInferencePipeline()
        result = pipeline.run(input_data)
    """

    def __init__(self):
        self.weight_service = WeightService()
        self.evidence_service = EvidenceSearchService()
        self.ranking_merger = RankingMerger()
        self.bucket_arbitrator = BucketArbitrator()

    @traceable(name="bucket_inference_pipeline")
    def run(self, input_data: BucketInferenceInput) -> Dict[str, BucketInferenceOutput]:
        """
        버킷 추론 실행

        Args:
            input_data: 버킷 추론 입력

        Returns:
            {부위코드: BucketInferenceOutput} 딕셔너리
        """
        results: Dict[str, BucketInferenceOutput] = {}

        for body_part in input_data.body_parts:
            bp_code = body_part.code

            # Step 1: 가중치 계산
            bucket_scores, weight_ranking = self.weight_service.calculate_scores(
                body_part
            )

            # Step 2: 벡터 검색
            query = self._build_search_query(body_part, input_data)
            evidence = self.evidence_service.search(
                query=query,
                body_part=bp_code,
            )
            search_ranking = self.evidence_service.get_search_ranking(evidence)

            # Step 3: 랭킹 통합
            merged_ranking = self.ranking_merger.merge(weight_ranking, search_ranking)

            # Step 4: LLM 버킷 중재
            result = self.bucket_arbitrator.arbitrate(
                body_part=body_part,
                bucket_scores=bucket_scores,
                weight_ranking=weight_ranking,
                search_ranking=search_ranking,
                evidence=evidence,
                user_input=input_data,
            )

            results[bp_code] = result

        return results

    def _build_search_query(
        self,
        body_part,
        user_input: BucketInferenceInput,
    ) -> str:
        """검색 쿼리 생성"""
        symptoms = body_part.symptoms[:5]  # 상위 5개

        demo = user_input.demographics
        query = (
            f"{demo.age}세 {demo.sex} 환자, "
            f"증상: {', '.join(symptoms)}"
        )

        # 자연어 입력이 있으면 추가
        if user_input.natural_language and user_input.natural_language.has_content:
            nl_text = user_input.natural_language.to_text()
            query += f"\n{nl_text}"

        return query

    def run_single(
        self,
        input_data: BucketInferenceInput,
        body_part_code: str,
    ) -> BucketInferenceOutput:
        """단일 부위 추론"""
        results = self.run(input_data)
        if body_part_code not in results:
            raise ValueError(f"부위 코드 '{body_part_code}'를 찾을 수 없습니다.")
        return results[body_part_code]
