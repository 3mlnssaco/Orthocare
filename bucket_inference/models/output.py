"""버킷 추론 출력 모델"""

from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class BucketScore(BaseModel):
    """버킷별 점수"""

    bucket: str = Field(..., description="버킷 코드 (OA, OVR, TRM, INF)")
    score: float = Field(..., description="가중치 합계 점수")
    percentage: float = Field(..., ge=0, le=100, description="백분율 (%)")
    contributing_symptoms: List[str] = Field(
        default_factory=list, description="점수에 기여한 증상들"
    )


class DiscrepancyAlert(BaseModel):
    """가중치 vs 검색 불일치 경고"""

    type: str = Field(..., description="불일치 유형")
    weight_ranking: List[str] = Field(..., description="가중치 기반 순위")
    search_ranking: List[str] = Field(..., description="검색 기반 순위")
    message: str = Field(..., description="경고 메시지")
    severity: str = Field(default="warning", description="심각도 (warning, critical)")


class RedFlagResult(BaseModel):
    """레드플래그 결과"""

    triggered: bool = Field(default=False, description="레드플래그 발동 여부")
    flags: List[str] = Field(default_factory=list, description="발동된 레드플래그 코드")
    messages: List[str] = Field(default_factory=list, description="경고 메시지")
    action: Optional[str] = Field(default=None, description="권장 조치")


class BucketInferenceOutput(BaseModel):
    """버킷 추론 출력

    API 응답: POST /api/v1/infer-bucket
    """

    # 기본 정보
    body_part: str = Field(..., description="부위 코드")

    # 버킷 결과
    final_bucket: str = Field(..., description="최종 진단 버킷 (OA/OVR/TRM/INF)")
    confidence: float = Field(..., ge=0, le=1, description="신뢰도 (0-1)")
    bucket_scores: Dict[str, float] = Field(
        default_factory=dict,
        description="버킷별 점수 {'OA': 15.0, 'OVR': 8.0, ...}"
    )

    # 랭킹 정보
    weight_ranking: List[str] = Field(..., description="가중치 기반 순위")
    search_ranking: List[str] = Field(
        default_factory=list, description="검색 기반 순위"
    )
    discrepancy: Optional[DiscrepancyAlert] = Field(
        default=None, description="불일치 경고"
    )

    # 근거 정보
    evidence_summary: str = Field(..., description="근거 요약 (LLM 생성)")
    llm_reasoning: str = Field(default="", description="LLM 판단 근거")

    # 레드플래그
    red_flag: Optional[RedFlagResult] = Field(
        default=None, description="레드플래그 결과"
    )

    # 메타데이터
    inferred_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="추론 시간"
    )

    @property
    def has_discrepancy(self) -> bool:
        """불일치 존재 여부"""
        return self.discrepancy is not None

    @property
    def has_red_flag(self) -> bool:
        """레드플래그 발동 여부"""
        return self.red_flag is not None and self.red_flag.triggered

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
