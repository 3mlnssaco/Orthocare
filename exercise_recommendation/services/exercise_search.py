"""운동용 벡터 검색 서비스

벡터 DB: orthocare-exercise
환자 상태/증상 기반 운동 검색
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import logging

from openai import OpenAI
from langsmith import traceable

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.utils import PineconeClient
from exercise_recommendation.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExerciseSearchResult:
    """운동 검색 결과"""
    exercise_id: str
    name_kr: str
    name_en: str
    difficulty: str
    bucket_tags: List[str]
    score: float
    metadata: Dict[str, Any]


class ExerciseSearchService:
    """운동용 벡터 검색 서비스

    버킷 + 증상 기반 유사 운동 검색
    """

    def __init__(
        self,
        pinecone_client: Optional[PineconeClient] = None,
        openai_client: Optional[OpenAI] = None,
    ):
        """
        Args:
            pinecone_client: Pinecone 클라이언트
            openai_client: OpenAI 클라이언트
        """
        self._pc = pinecone_client
        self._openai = openai_client or OpenAI()
        self._min_score = settings.min_search_score
        self._top_k = settings.search_top_k

    def _get_client(self) -> PineconeClient:
        """Pinecone 클라이언트 반환 (지연 초기화)"""
        if self._pc is None:
            self._pc = PineconeClient(index_name=settings.pinecone_index)
        return self._pc

    def _embed(self, text: str) -> List[float]:
        """텍스트 임베딩"""
        response = self._openai.embeddings.create(
            model=settings.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    @traceable(name="exercise_symptom_search")
    def search_by_symptoms(
        self,
        symptoms: List[str],
        body_part: str,
        bucket: str,
        demographics: Optional[Dict] = None,
    ) -> List[ExerciseSearchResult]:
        """
        증상 기반 운동 검색

        Args:
            symptoms: 증상 목록
            body_part: 부위 코드
            bucket: 진단 버킷
            demographics: 인구통계 정보

        Returns:
            검색 결과 목록
        """
        client = self._get_client()

        # 쿼리 생성
        query = self._build_query(symptoms, body_part, bucket, demographics)
        query_vector = self._embed(query)

        # 필터 구성
        filters = {
            "body_part": body_part,
            "source": "exercise",
        }

        # 벡터 검색
        raw_results = client.query(
            vector=query_vector,
            top_k=self._top_k,
            filter=filters,
            min_score=self._min_score,
        )

        # 결과 변환
        results = []
        for item in raw_results.items:
            metadata = item.metadata

            # 버킷 태그 파싱
            bucket_value = metadata.get("bucket", "")
            bucket_tags = [
                b.strip() for b in bucket_value.split(",") if b.strip()
            ]

            # 버킷 매칭 체크
            if bucket not in bucket_tags:
                continue

            results.append(
                ExerciseSearchResult(
                    exercise_id=metadata.get("id", item.id),
                    name_kr=metadata.get("name_kr", ""),
                    name_en=metadata.get("name_en", ""),
                    difficulty=metadata.get("difficulty", "medium"),
                    bucket_tags=bucket_tags,
                    score=item.score,
                    metadata=metadata,
                )
            )

        # 점수순 정렬
        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def _build_query(
        self,
        symptoms: List[str],
        body_part: str,
        bucket: str,
        demographics: Optional[Dict] = None,
    ) -> str:
        """검색 쿼리 생성"""
        parts = [
            f"부위: {body_part}",
            f"버킷: {bucket}",
            f"증상: {', '.join(symptoms[:5])}",
        ]

        if demographics:
            age = demographics.get("age")
            if age:
                if age >= 65:
                    parts.append("고령자 안전 운동")
                elif age >= 50:
                    parts.append("중년 적합 운동")

        return " ".join(parts)

    @traceable(name="find_similar_exercises")
    def search_similar_exercises(
        self,
        exercise_id: str,
        body_part: str,
        top_k: int = 5,
    ) -> List[ExerciseSearchResult]:
        """
        유사 운동 검색 (대체 운동 추천용)

        Args:
            exercise_id: 기준 운동 ID
            body_part: 부위 코드
            top_k: 결과 수

        Returns:
            유사 운동 목록
        """
        client = self._get_client()

        # 기준 운동 조회
        # TODO: 기준 운동의 벡터를 가져와서 유사 검색
        # 현재는 간단히 같은 부위 운동 반환

        filters = {
            "body_part": body_part,
            "source": "exercise",
        }

        # 부위 기반 검색
        query = f"{body_part} 재활 운동"
        query_vector = self._embed(query)

        raw_results = client.query(
            vector=query_vector,
            top_k=top_k + 1,  # 자기 자신 제외
            filter=filters,
            min_score=self._min_score,
        )

        results = []
        for item in raw_results.items:
            metadata = item.metadata
            if metadata.get("id") == exercise_id:
                continue

            bucket_value = metadata.get("bucket", "")
            bucket_tags = [
                b.strip() for b in bucket_value.split(",") if b.strip()
            ]

            results.append(
                ExerciseSearchResult(
                    exercise_id=metadata.get("id", item.id),
                    name_kr=metadata.get("name_kr", ""),
                    name_en=metadata.get("name_en", ""),
                    difficulty=metadata.get("difficulty", "medium"),
                    bucket_tags=bucket_tags,
                    score=item.score,
                    metadata=metadata,
                )
            )

        return results[:top_k]
