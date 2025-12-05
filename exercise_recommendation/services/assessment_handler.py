"""사후 설문 처리 서비스

케이스별 처리:
1. fresh_start: 최초 운동 (사전 평가만 사용)
2. normal: 정상 운동 (이전 기록 반영, 3세션 완료 시 조정)
3. reset: 오랜만 (7일+) 또는 기록 손실 (리셋)
"""

from typing import List, Optional
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from exercise_recommendation.models.input import PostAssessmentResult
from exercise_recommendation.models.assessment import (
    AssessmentProcessResult,
    DifficultyAdjustment,
    SessionCycleResult,
)
from exercise_recommendation.config import settings


class AssessmentHandler:
    """사후 설문 처리 서비스"""

    def __init__(
        self,
        stale_threshold_days: int = None,
        cycle_count: int = None,
    ):
        """
        Args:
            stale_threshold_days: 오랜만 판단 기준 (일)
            cycle_count: 난이도 조정 사이클 (세션 수)
        """
        self.stale_threshold_days = (
            stale_threshold_days or settings.stale_threshold_days
        )
        self.cycle_count = cycle_count or settings.session_cycle_count

    def process(
        self,
        previous_assessments: Optional[List[PostAssessmentResult]],
        last_assessment_date: Optional[datetime],
    ) -> AssessmentProcessResult:
        """
        사후 설문 처리

        Args:
            previous_assessments: 이전 사후 설문 기록 (최대 3세션)
            last_assessment_date: 마지막 사후 설문 날짜

        Returns:
            AssessmentProcessResult
        """
        # 케이스 1: 최초 운동
        if not previous_assessments:
            return AssessmentProcessResult(
                status="fresh_start",
                adjustments=None,
                message="첫 운동입니다. 사전 평가 결과를 기반으로 추천합니다.",
                sessions_analyzed=0,
            )

        # 케이스 3: 오랜만
        if last_assessment_date:
            days_since = (datetime.now() - last_assessment_date).days
            if days_since >= self.stale_threshold_days:
                return AssessmentProcessResult(
                    status="reset",
                    adjustments=None,
                    message=f"{days_since}일만입니다. 이전 기록을 리셋하고 새로 시작합니다.",
                    sessions_analyzed=0,
                    days_since_last=days_since,
                )
        else:
            days_since = None

        # 케이스 4: 정상 - 3세션 사이클 완료 시 조정 계산
        sessions_count = len(previous_assessments)

        if sessions_count >= self.cycle_count:
            # 최근 3세션으로 사이클 분석
            cycle = SessionCycleResult(
                sessions=previous_assessments[-self.cycle_count:]
            )
            adjustments = cycle.get_adjustments()
            trend = cycle.get_trend()
            avg_rpe = cycle.average_rpe

            # 완수율 계산
            completion_rates = [
                s.completion_rate for s in previous_assessments
                if s.completion_rate is not None
            ]
            avg_completion = (
                sum(completion_rates) / len(completion_rates)
                if completion_rates else None
            )

            if adjustments.has_changes:
                message = self._generate_adjustment_message(adjustments, avg_rpe)
            else:
                message = "이전 기록을 분석한 결과, 현재 난이도가 적절합니다."

            return AssessmentProcessResult(
                status="normal",
                adjustments=adjustments,
                message=message,
                sessions_analyzed=sessions_count,
                days_since_last=days_since,
                average_rpe=avg_rpe,
                trend_direction=trend,
                completion_rate_avg=avg_completion,
            )
        else:
            # 3세션 미만 - 조정 없이 유지
            avg_rpe = sum(s.total_rpe_score for s in previous_assessments) / sessions_count

            return AssessmentProcessResult(
                status="normal",
                adjustments=None,
                message=f"{sessions_count}세션 완료. "
                        f"{self.cycle_count - sessions_count}세션 후 난이도가 조정됩니다.",
                sessions_analyzed=sessions_count,
                days_since_last=days_since,
                average_rpe=avg_rpe,
            )

    def _generate_adjustment_message(
        self,
        adjustments: DifficultyAdjustment,
        avg_rpe: float,
    ) -> str:
        """조정 메시지 생성"""
        if adjustments.difficulty_delta > 0:
            return (
                f"평균 RPE {avg_rpe:.1f}점으로 운동이 쉬웠습니다. "
                "난이도를 올립니다."
            )
        elif adjustments.difficulty_delta < 0:
            return (
                f"평균 RPE {avg_rpe:.1f}점으로 운동이 힘들었습니다. "
                "난이도를 낮춥니다."
            )
        else:
            return "현재 난이도가 적절합니다."

    def should_show_assessment_prompt(
        self,
        previous_assessments: Optional[List[PostAssessmentResult]],
    ) -> bool:
        """사후 설문 프롬프트 표시 여부"""
        if not previous_assessments:
            return False

        sessions_count = len(previous_assessments)
        # 3세션 사이클 직전에 알림
        return sessions_count > 0 and (sessions_count + 1) % self.cycle_count == 0
