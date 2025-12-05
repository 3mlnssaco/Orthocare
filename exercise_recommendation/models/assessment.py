"""사후 설문 처리 결과 모델"""

from typing import Optional, Dict, Literal, List
from pydantic import BaseModel, Field


class DifficultyAdjustment(BaseModel):
    """난이도 조정 정보"""

    difficulty_delta: int = Field(
        default=0, ge=-2, le=2,
        description="난이도 변화 (-2: 많이 쉽게, +2: 많이 어렵게)"
    )
    sets_delta: int = Field(
        default=0, ge=-2, le=2,
        description="세트 수 변화"
    )
    reps_delta: int = Field(
        default=0, ge=-5, le=5,
        description="반복 횟수 변화"
    )
    rest_delta: int = Field(
        default=0, ge=-15, le=15,
        description="휴식 시간 변화 (초)"
    )

    @property
    def has_changes(self) -> bool:
        """변경 사항 존재 여부"""
        return any([
            self.difficulty_delta != 0,
            self.sets_delta != 0,
            self.reps_delta != 0,
            self.rest_delta != 0,
        ])


class AssessmentProcessResult(BaseModel):
    """사후 설문 처리 결과

    케이스:
    1. fresh_start: 최초 운동 (사전 평가만 사용)
    2. normal: 정상 운동 (이전 기록 반영)
    3. reset: 오랜만 (7일+) 또는 기록 손실 (리셋)
    """

    status: Literal["fresh_start", "normal", "reset"] = Field(
        ..., description="처리 상태"
    )
    adjustments: Optional[DifficultyAdjustment] = Field(
        default=None, description="난이도 조정 (status=normal일 때만)"
    )
    message: str = Field(..., description="처리 메시지")

    # 분석 정보
    sessions_analyzed: int = Field(default=0, description="분석된 세션 수")
    days_since_last: Optional[int] = Field(
        default=None, description="마지막 세션 이후 경과 일수"
    )
    average_rpe: Optional[float] = Field(
        default=None, description="평균 RPE 점수 (3-15)"
    )

    # 세부 분석
    trend_direction: Optional[Literal["improving", "stable", "declining"]] = Field(
        default=None, description="개선 추세"
    )
    completion_rate_avg: Optional[float] = Field(
        default=None, ge=0, le=1, description="평균 완수율"
    )


class SessionCycleResult(BaseModel):
    """3세션 사이클 분석 결과"""

    sessions: List["PostAssessmentResult"] = Field(
        ..., min_length=3, max_length=3, description="3세션 데이터"
    )

    @property
    def average_difficulty(self) -> float:
        """평균 난이도 체감"""
        return sum(s.difficulty_felt for s in self.sessions) / 3

    @property
    def average_muscle_stimulus(self) -> float:
        """평균 근육 자극"""
        return sum(s.muscle_stimulus for s in self.sessions) / 3

    @property
    def average_sweat_level(self) -> float:
        """평균 땀 배출량"""
        return sum(s.sweat_level for s in self.sessions) / 3

    @property
    def average_rpe(self) -> float:
        """평균 RPE 총점"""
        return sum(s.total_rpe_score for s in self.sessions) / 3

    def get_adjustments(self) -> DifficultyAdjustment:
        """
        RPE 기반 난이도 조정 계산

        규칙:
        - 평균 RPE < 7: 난이도 올림 (너무 쉬움)
        - 평균 RPE 7-11: 유지 (적정)
        - 평균 RPE > 11: 난이도 내림 (너무 힘듦)
        """
        avg_rpe = self.average_rpe

        if avg_rpe < 7:
            # 너무 쉬움 → 난이도 올림
            return DifficultyAdjustment(
                difficulty_delta=1,
                sets_delta=1,
                reps_delta=2,
                rest_delta=-10,
            )
        elif avg_rpe > 11:
            # 너무 힘듦 → 난이도 내림
            return DifficultyAdjustment(
                difficulty_delta=-1,
                sets_delta=-1,
                reps_delta=-2,
                rest_delta=10,
            )
        else:
            # 적정 → 유지
            return DifficultyAdjustment()

    def get_trend(self) -> Literal["improving", "stable", "declining"]:
        """개선 추세 분석"""
        # 첫 세션 vs 마지막 세션 비교
        first = self.sessions[0].total_rpe_score
        last = self.sessions[-1].total_rpe_score

        if last < first - 1:
            return "improving"  # RPE 감소 = 체력 향상
        elif last > first + 1:
            return "declining"  # RPE 증가 = 체력 저하
        else:
            return "stable"


# Forward reference 해결
from exercise_recommendation.models.input import PostAssessmentResult
SessionCycleResult.model_rebuild()
