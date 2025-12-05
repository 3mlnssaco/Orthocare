"""진단용 근거 검색 서비스

벡터 DB: orthocare-diagnosis
소스: verified_paper, orthobullets, pubmed
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from openai import OpenAI
from langsmith import traceable

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.utils import PineconeClient
from bucket_inference.config import settings


@dataclass
class Paper:
    """논문/문서 정보"""
    doc_id: str
    title: str
    source_type: str  # verified_paper, orthobullets, pubmed
    source_layer: int  # 1, 2, 3
    body_part: str
    bucket_tags: List[str]
    content: str
    year: Optional[int] = None
    url: Optional[str] = None


@dataclass
class SearchResult:
    """검색 결과"""
    paper: Paper
    similarity_score: float
    matching_reason: str


@dataclass
class EvidenceResult:
    """근거 검색 결과"""
    query: str
    body_part: str
    results: List[SearchResult]
    search_timestamp: datetime

    def get_top_results(self, n: int = 5) -> List[SearchResult]:
        """상위 n개 결과 반환"""
        return self.results[:n]


class EvidenceSearchService:
    """
    진단용 3-Layer 근거 검색

    Layer 1: 검증된 논문 (verified_paper) - 최고 신뢰도
    Layer 2: Orthobullets (orthobullets) - 높은 신뢰도
    Layer 3: PubMed (pubmed) - 중간 신뢰도
    """

    def __init__(
        self,
        pinecone_client: Optional[PineconeClient] = None,
        openai_client: Optional[OpenAI] = None,
    ):
        """
        Args:
            pinecone_client: Pinecone 클라이언트 (없으면 자동 생성)
            openai_client: OpenAI 클라이언트 (임베딩용)
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

    @traceable(name="evidence_vector_search")
    def search(
        self,
        query: str,
        body_part: str,
        buckets: Optional[List[str]] = None,
    ) -> EvidenceResult:
        """
        벡터 검색 수행

        Args:
            query: 검색 쿼리
            body_part: 부위 코드
            buckets: 필터링할 버킷 리스트 (선택)

        Returns:
            EvidenceResult 객체
        """
        client = self._get_client()

        # 쿼리 임베딩
        query_vector = self._embed(query)

        # 필터 구성
        filters = {"body_part": body_part}

        # 벡터 검색
        raw_results = client.query(
            vector=query_vector,
            top_k=self._top_k,
            filter=filters,
            min_score=self._min_score,
        )

        # SearchResult로 변환
        results = []
        for item in raw_results.items:
            metadata = item.metadata

            # 소스 타입에 따른 레이어 결정
            source = metadata.get("source", "paper")
            if source == "verified_paper":
                source_type = "verified_paper"
                source_layer = 1
            elif source == "orthobullets":
                source_type = "orthobullets"
                source_layer = 2
            elif source == "pubmed":
                source_type = "pubmed"
                source_layer = 3
            else:
                source_type = "verified_paper"
                source_layer = 1

            # 버킷 태그 파싱
            bucket_value = metadata.get("bucket", "")
            if bucket_value and bucket_value != "research":
                bucket_tags = [b.strip() for b in bucket_value.split(",") if b.strip()]
            else:
                bucket_tags = []

            paper = Paper(
                doc_id=item.id,
                title=metadata.get("title", "제목 없음"),
                source_type=source_type,
                source_layer=source_layer,
                body_part=body_part,
                bucket_tags=bucket_tags,
                content=metadata.get("text", ""),
                year=metadata.get("year"),
                url=metadata.get("url"),
            )

            results.append(
                SearchResult(
                    paper=paper,
                    similarity_score=item.score,
                    matching_reason=f"'{paper.title[:30]}...' (유사도: {item.score:.2f})",
                )
            )

        # 유사도 기준 정렬
        results.sort(key=lambda x: x.similarity_score, reverse=True)

        return EvidenceResult(
            query=query,
            body_part=body_part,
            results=results,
            search_timestamp=datetime.now(),
        )

    def get_bucket_distribution(self, evidence: EvidenceResult) -> List[tuple]:
        """검색 결과의 버킷 분포 반환"""
        bucket_counts: Dict[str, int] = {}

        for result in evidence.results:
            for bucket in result.paper.bucket_tags:
                bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

        # 카운트 내림차순 정렬
        return sorted(bucket_counts.items(), key=lambda x: x[1], reverse=True)

    def get_search_ranking(self, evidence: EvidenceResult) -> List[str]:
        """검색 결과 기반 버킷 순위"""
        distribution = self.get_bucket_distribution(evidence)
        return [bucket for bucket, _ in distribution]
