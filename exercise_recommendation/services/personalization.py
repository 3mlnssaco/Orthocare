"""개인화 조정 서비스

나이, 통증, 신체 점수 기반 개인화
"""

from typing import List, Dict, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.models import Demographics


class PersonalizationService:
    """개인화 조정 서비스"""

    def apply(
        self,
        exercises: List[Dict],
        demographics: Demographics,
        nrs: int,
        skipped_exercises: Optional[List[str]] = None,
        favorite_exercises: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        개인화 조정 적용

        Args:
            exercises: 운동 목록
            demographics: 인구통계 정보
            nrs: 통증 점수
            skipped_exercises: 자주 건너뛴 운동 ID
            favorite_exercises: 즐겨찾기 운동 ID

        Returns:
            조정된 운동 목록
        """
        personalized = []

        for ex in exercises:
            adjusted = ex.copy()

            # 나이 기반 조정
            adjusted = self._adjust_for_age(adjusted, demographics.age)

            # 통증 기반 조정
            adjusted = self._adjust_for_pain(adjusted, nrs)

            # 자주 건너뛴 운동 우선순위 하락
            if skipped_exercises and ex.get("id") in skipped_exercises:
                adjusted["_priority_penalty"] = 0.1

            # 즐겨찾기 운동 우선순위 상승
            if favorite_exercises and ex.get("id") in favorite_exercises:
                adjusted["_priority_boost"] = 0.2

            personalized.append(adjusted)

        # 우선순위 정렬
        personalized.sort(
            key=lambda x: (
                x.get("_priority_boost", 0) - x.get("_priority_penalty", 0)
            ),
            reverse=True,
        )

        return personalized

    def _adjust_for_age(self, exercise: Dict, age: int) -> Dict:
        """나이 기반 조정"""
        adjusted = exercise.copy()

        if age >= 65:
            # 고령자: 세트 수 감소, 휴식 증가
            current_sets = exercise.get("sets", 2)
            adjusted["sets"] = max(1, current_sets - 1)

            rest_str = exercise.get("rest", "30초")
            current_rest = int(rest_str.replace("초", "").strip())
            adjusted["rest"] = f"{current_rest + 15}초"

            adjusted["_age_adjustment"] = "elderly_safe"

        elif age >= 50:
            # 중년: 휴식 약간 증가
            rest_str = exercise.get("rest", "30초")
            current_rest = int(rest_str.replace("초", "").strip())
            adjusted["rest"] = f"{current_rest + 10}초"

            adjusted["_age_adjustment"] = "moderate"

        return adjusted

    def _adjust_for_pain(self, exercise: Dict, nrs: int) -> Dict:
        """통증 기반 조정"""
        adjusted = exercise.copy()

        if nrs >= 7:
            # 심한 통증: 세트 및 반복 감소
            current_sets = exercise.get("sets", 2)
            adjusted["sets"] = max(1, current_sets - 1)

            reps_str = exercise.get("reps", "10회")
            import re
            match = re.search(r"(\d+)", reps_str)
            if match:
                current_reps = int(match.group(1))
                adjusted["reps"] = f"{max(5, current_reps - 3)}회"

            adjusted["_pain_adjustment"] = "reduced_intensity"

        elif nrs >= 4:
            # 중등도 통증: 반복 약간 감소
            reps_str = exercise.get("reps", "10회")
            import re
            match = re.search(r"(\d+)", reps_str)
            if match:
                current_reps = int(match.group(1))
                adjusted["reps"] = f"{max(5, current_reps - 2)}회"

            adjusted["_pain_adjustment"] = "moderate_intensity"

        return adjusted

    def get_exercise_order(self, exercises: List[Dict]) -> List[Dict]:
        """
        운동 순서 결정 (가동성 → 근력 → 균형)
        """
        order_priority = {
            "Mobility": 0,
            "Stretching": 1,
            "Strengthening": 2,
            "Stability": 3,
            "Balance": 4,
        }

        def get_priority(ex: Dict) -> int:
            tags = ex.get("function_tags", [])
            priorities = [order_priority.get(t, 5) for t in tags]
            return min(priorities) if priorities else 5

        return sorted(exercises, key=get_priority)
