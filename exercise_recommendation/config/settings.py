"""Exercise Recommendation 설정

환경 변수:
- OPENAI_API_KEY: OpenAI API 키
- PINECONE_API_KEY: Pinecone API 키
- PINECONE_INDEX: Pinecone 인덱스명 (기본값: orthocare-exercise)
"""

import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class ExerciseRecommendationSettings(BaseSettings):
    """운동 추천 설정"""

    # API Keys
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    pinecone_api_key: str = Field(default="", description="Pinecone API Key")

    # Pinecone
    pinecone_index: str = Field(
        default="orthocare-exercise",
        description="운동용 벡터 DB 인덱스"
    )

    # OpenAI
    openai_model: str = Field(default="gpt-4o", description="LLM 모델")
    embedding_model: str = Field(
        default="text-embedding-3-large",
        description="임베딩 모델"
    )

    # 검색 설정
    min_search_score: float = Field(default=0.35, description="최소 유사도 점수")
    search_top_k: int = Field(default=20, description="검색 결과 수")

    # 사후 설문 설정
    stale_threshold_days: int = Field(
        default=7,
        description="사후 설문 유효 기간 (일)"
    )
    session_cycle_count: int = Field(
        default=3,
        description="난이도 조정 사이클 (세션 수)"
    )

    # 운동 추천 설정
    min_exercises: int = Field(default=4, description="최소 운동 수")
    max_exercises: int = Field(default=8, description="최대 운동 수")

    # 데이터 경로
    data_dir: Path = Field(
        default=Path(__file__).parent.parent.parent / "data",
        description="데이터 디렉토리"
    )

    # 서버 설정
    host: str = Field(default="0.0.0.0", description="호스트")
    port: int = Field(default=8000, description="포트")

    class Config:
        env_prefix = ""
        env_file = ".env"
        extra = "ignore"


settings = ExerciseRecommendationSettings()
