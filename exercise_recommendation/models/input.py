"""운동 추천 입력 모델

사후 설문 데이터 포함 - 앱에서 전달받음
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.models import Demographics, PhysicalScore


class PostAssessmentResult(BaseModel):
    """사후 설문 결과 (앱에서 수집)

    RPE 기반 3문항:
    1. 운동 난이도 체감 (1-5)
    2. 근육 자극 정도 (1-5)
    3. 땀 배출량 (1-5)
    """

    session_date: datetime = Field(..., description="세션 날짜")

    # RPE 기반 3문항
    difficulty_felt: int = Field(
        ..., ge=1, le=5,
        description="운동 난이도 체감 (1: 매우 쉬움 ~ 5: 매우 힘듦)"
    )
    muscle_stimulus: int = Field(
        ..., ge=1, le=5,
        description="근육 자극 정도 (1: 전혀 없음 ~ 5: 매우 강함)"
    )
    sweat_level: int = Field(
        ..., ge=1, le=5,
        description="땀 배출량 (1: 전혀 없음 ~ 5: 매우 많음)"
    )

    # 선택 항목
    pain_during_exercise: Optional[int] = Field(
        default=None, ge=0, le=10,
        description="운동 중 통증 (NRS 0-10)"
    )
    skipped_exercises: List[str] = Field(
        default_factory=list,
        description="건너뛴 운동 ID 목록"
    )
    completed_sets: Optional[int] = Field(
        default=None,
        description="완료한 세트 수"
    )
    total_sets: Optional[int] = Field(
        default=None,
        description="총 세트 수"
    )

    @property
    def total_rpe_score(self) -> int:
        """RPE 총점 (3-15)"""
        return self.difficulty_felt + self.muscle_stimulus + self.sweat_level

    @property
    def completion_rate(self) -> Optional[float]:
        """완수율 (0.0-1.0)"""
        if self.total_sets and self.completed_sets is not None:
            return self.completed_sets / self.total_sets
        return None


class ExerciseRecommendationInput(BaseModel):
    """운동 추천 입력

    API 엔드포인트: POST /api/v1/recommend-exercises
    사용 빈도: 매일

    예시:
    {
        "user_id": "user_123",
        "body_part": "knee",
        "bucket": "OA",
        "physical_score": {"total_score": 12},
        "demographics": {"age": 55, "sex": "male", ...},
        "nrs": 5,
        "previous_assessments": [...],
        "last_assessment_date": "2025-11-29T10:00:00"
    }
    """

    # === 필수 ===
    user_id: str = Field(..., description="사용자 ID")
    body_part: str = Field(..., description="부위 코드 (knee, shoulder 등)")
    bucket: str = Field(..., description="버킷 추론 결과 (OA/OVR/TRM/INF)")

    # === 사전 평가 결과 ===
    physical_score: PhysicalScore = Field(..., description="신체 점수 (Lv A/B/C/D)")
    demographics: Demographics = Field(..., description="인구통계학적 정보")
    nrs: int = Field(..., ge=0, le=10, description="통증 점수 (0-10)")

    # === 사후 설문 데이터 (Optional) ===
    previous_assessments: Optional[List[PostAssessmentResult]] = Field(
        default=None,
        description="최근 사후 설문 기록 (최대 3세션)"
    )
    last_assessment_date: Optional[datetime] = Field(
        default=None,
        description="마지막 사후 설문 날짜"
    )

    # === 운동 중 데이터 (Optional) ===
    exercise_duration_history: Optional[List[int]] = Field(
        default=None,
        description="운동 시간 기록 (분)"
    )
    skipped_exercises: Optional[List[str]] = Field(
        default=None,
        description="자주 건너뛴 운동 ID"
    )
    favorite_exercises: Optional[List[str]] = Field(
        default=None,
        description="즐겨찾기 운동 ID"
    )

    @property
    def is_first_session(self) -> bool:
        """최초 운동 여부"""
        return self.previous_assessments is None or len(self.previous_assessments) == 0

    @property
    def has_valid_assessments(self) -> bool:
        """유효한 사후 설문 존재 여부"""
        return (
            self.previous_assessments is not None
            and len(self.previous_assessments) > 0
        )
