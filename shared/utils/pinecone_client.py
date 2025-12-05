"""Pinecone 벡터 DB 클라이언트 (공유)"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from pinecone import Pinecone


@dataclass
class SearchResult:
    """검색 결과"""

    id: str
    score: float
    metadata: Dict[str, Any]


@dataclass
class SearchResults:
    """검색 결과 목록"""

    items: List[SearchResult]
    query: str
    total_count: int

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)


class PineconeClient:
    """Pinecone 벡터 DB 클라이언트

    사용 예시:
        client = PineconeClient(index_name="orthocare-diagnosis")
        results = client.query(
            vector=embedding,
            top_k=10,
            filter={"body_part": "knee"}
        )
    """

    def __init__(
        self,
        index_name: str,
        api_key: Optional[str] = None,
        namespace: str = "",
    ):
        """
        Args:
            index_name: Pinecone 인덱스 이름
            api_key: Pinecone API 키 (없으면 환경변수에서 로드)
            namespace: 네임스페이스 (기본값: 빈 문자열)
        """
        self.index_name = index_name
        self.namespace = namespace

        api_key = api_key or os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY가 설정되지 않았습니다.")

        self._pc = Pinecone(api_key=api_key)
        self._index = self._pc.Index(index_name)

    def query(
        self,
        vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
        min_score: float = 0.0,
    ) -> SearchResults:
        """벡터 검색

        Args:
            vector: 쿼리 벡터 (임베딩)
            top_k: 반환할 최대 결과 수
            filter: 메타데이터 필터
            include_metadata: 메타데이터 포함 여부
            min_score: 최소 유사도 점수

        Returns:
            SearchResults: 검색 결과
        """
        response = self._index.query(
            vector=vector,
            top_k=top_k,
            filter=filter,
            include_metadata=include_metadata,
            namespace=self.namespace,
        )

        items = []
        for match in response.matches:
            if match.score >= min_score:
                items.append(
                    SearchResult(
                        id=match.id,
                        score=match.score,
                        metadata=match.metadata or {},
                    )
                )

        return SearchResults(
            items=items,
            query="",  # 원본 쿼리 텍스트는 호출자가 설정
            total_count=len(items),
        )

    def upsert(
        self,
        vectors: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """벡터 업서트

        Args:
            vectors: 벡터 목록 [{"id": str, "values": List[float], "metadata": Dict}]
            batch_size: 배치 크기

        Returns:
            업서트된 벡터 수
        """
        count = 0
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i : i + batch_size]
            self._index.upsert(vectors=batch, namespace=self.namespace)
            count += len(batch)
        return count

    def delete(
        self,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict[str, Any]] = None,
        delete_all: bool = False,
    ) -> None:
        """벡터 삭제

        Args:
            ids: 삭제할 벡터 ID 목록
            filter: 메타데이터 필터로 삭제
            delete_all: 전체 삭제
        """
        if delete_all:
            self._index.delete(delete_all=True, namespace=self.namespace)
        elif ids:
            self._index.delete(ids=ids, namespace=self.namespace)
        elif filter:
            self._index.delete(filter=filter, namespace=self.namespace)

    def describe_stats(self) -> Dict[str, Any]:
        """인덱스 통계 반환"""
        return self._index.describe_index_stats()
