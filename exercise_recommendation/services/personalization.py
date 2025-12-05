"""개인화 조정 서비스

나이, 통증, 신체 점수 기반 개인화
"""

from typing import List, Dict, Optional

from langsmith import traceable

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.models import Demographics


class PersonalizationService:
    """개인화 조정 서비스"""

    @traceable(name="exercise_personalization")
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

            # BMI 기반 조정 (신규)
            adjusted = self._adjust_for_bmi(adjusted, demographics.bmi)

            # 통증 기반 조정
            adjusted = self._adjust_for_pain(adjusted, nrs)

            # 자주 건너뛴 운동 우선순위 하락
            if skipped_exercises and ex.get("id") in skipped_exercises:
                adjusted["_priority_penalty"] = 0.1

            # 즐겨찾기 운동 우선순위 상승
            if favorite_exercises and ex.get("id") in favorite_exercises:
                adjusted["_priority_boost"] = 0.2

            # 환자 프로필에 맞는 운동 우선순위 상승
            adjusted = self._boost_appropriate_exercises(adjusted, demographics, nrs)

            personalized.append(adjusted)

        # 우선순위 정렬
        personalized.sort(
            key=lambda x: (
                x.get("_priority_boost", 0) - x.get("_priority_penalty", 0)
            ),
            reverse=True,
        )

        return personalized

    def _adjust_for_bmi(self, exercise: Dict, bmi: float) -> Dict:
        """BMI 기반 조정"""
        adjusted = exercise.copy()
        function_tags = exercise.get("function_tags", [])

        if bmi >= 30:
            # 비만: 체중 부하 운동 강도 감소
            if "Strengthening" in function_tags:
                current_sets = exercise.get("sets", 2)
                adjusted["sets"] = max(1, current_sets - 1)
                adjusted["_bmi_adjustment"] = "reduced_load"

            # 휴식 시간 증가
            rest_str = exercise.get("rest", "30초")
            import re
            match = re.search(r"(\d+)", rest_str)
            if match:
                current_rest = int(match.group(1))
                adjusted["rest"] = f"{current_rest + 15}초"

        elif bmi >= 25:
            # 과체중: 휴식 시간 약간 증가
            rest_str = exercise.get("rest", "30초")
            import re
            match = re.search(r"(\d+)", rest_str)
            if match:
                current_rest = int(match.group(1))
                adjusted["rest"] = f"{current_rest + 5}초"
            adjusted["_bmi_adjustment"] = "moderate"

        return adjusted

    def _boost_appropriate_exercises(
        self,
        exercise: Dict,
        demographics: Demographics,
        nrs: int,
    ) -> Dict:
        """환자 프로필에 맞는 운동 우선순위 상승"""
        adjusted = exercise.copy()
        function_tags = exercise.get("function_tags", [])
        difficulty = exercise.get("difficulty", "medium")
        boost = adjusted.get("_priority_boost", 0)

        age = demographics.age
        bmi = demographics.bmi

        # 고령자: 균형/안정성 운동 우선
        if age >= 65:
            if "Balance" in function_tags or "Stability" in function_tags:
                boost += 0.15
            if difficulty == "low":
                boost += 0.1

        # 비만: 저충격 운동 우선
        if bmi >= 30:
            if "Mobility" in function_tags or "Stretching" in function_tags:
                boost += 0.1
            if difficulty == "low":
                boost += 0.05

        # 고통증: 가동성 운동 우선
        if nrs >= 6:
            if "Mobility" in function_tags:
                boost += 0.15
            if difficulty == "low":
                boost += 0.1

        # 젊은 층 + 저통증: 근력 운동 우선
        if age < 40 and nrs < 4:
            if "Strengthening" in function_tags:
                boost += 0.1

        adjusted["_priority_boost"] = boost
        return adjusted

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

    @traceable(name="exercise_ordering")
    def get_exercise_order(self, exercises: List[Dict]) -> List[Dict]:
        """
        운동 순서 결정 (준비운동 → 가동성 → 근력 → 안정성 → 정리)

        원칙:
        1. 준비 운동 (Mobility, Stretching) → 먼저
        2. 본 운동 (Strengthening) → 중간
        3. 마무리 (Balance, Stability) → 마지막
        4. 같은 카테고리 내에서는 난이도 오름차순
        """
        # 기능별 우선순위
        category_priority = {
            "Mobility": 0,      # 준비 - 가동성
            "Stretching": 1,    # 준비 - 스트레칭
            "Strengthening": 2, # 본 - 근력
            "Stability": 3,     # 마무리 - 안정성
            "Balance": 4,       # 마무리 - 균형
        }

        # 난이도별 우선순위 (같은 기능 내 정렬용)
        difficulty_priority = {
            "low": 0,
            "medium": 1,
            "high": 2,
        }

        def get_sort_key(ex: Dict) -> tuple:
            # 기능 태그에서 가장 높은 우선순위 찾기
            tags = ex.get("function_tags", [])
            cat_priorities = [category_priority.get(t, 5) for t in tags]
            min_cat_priority = min(cat_priorities) if cat_priorities else 5

            # 난이도 우선순위
            difficulty = ex.get("difficulty", "medium")
            diff_priority = difficulty_priority.get(difficulty, 1)

            # 개인화 우선순위 (높을수록 먼저)
            boost = ex.get("_priority_boost", 0)

            return (min_cat_priority, diff_priority, -boost)

        ordered = sorted(exercises, key=get_sort_key)

        # 순서 인덱스 추가 (디버깅/추적용)
        for i, ex in enumerate(ordered):
            ex["_order_index"] = i + 1

        return ordered

    def ensure_category_balance(
        self,
        exercises: List[Dict],
        min_per_category: int = 1,
    ) -> List[Dict]:
        """
        카테고리 균형 확인 및 조정

        최소한 각 카테고리에서 min_per_category개씩 포함되도록 함
        """
        categories = {
            "warmup": ["Mobility", "Stretching"],
            "main": ["Strengthening"],
            "cooldown": ["Stability", "Balance"],
        }

        category_counts = {"warmup": 0, "main": 0, "cooldown": 0}

        for ex in exercises:
            tags = ex.get("function_tags", [])
            for cat_name, cat_tags in categories.items():
                if any(t in cat_tags for t in tags):
                    category_counts[cat_name] += 1

        # 카테고리별 부족 여부 체크
        missing = {
            cat: max(0, min_per_category - count)
            for cat, count in category_counts.items()
        }

        return exercises  # 현재는 체크만, 추후 자동 추가 로직 구현 가능
