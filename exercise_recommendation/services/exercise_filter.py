"""버킷 기반 운동 필터링 서비스"""

from typing import List, Dict, Tuple, Optional
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.models import PhysicalScore
from exercise_recommendation.models.output import RecommendedExercise, ExcludedExercise
from exercise_recommendation.models.assessment import DifficultyAdjustment
from exercise_recommendation.config import settings


class ExerciseFilter:
    """버킷 기반 운동 필터링"""

    def __init__(self):
        self._exercise_cache = {}

    def _load_exercises(self, body_part: str) -> List[Dict]:
        """운동 데이터 로드"""
        if body_part in self._exercise_cache:
            return self._exercise_cache[body_part]

        exercises_path = settings.data_dir / "exercise" / body_part / "exercises.json"

        if not exercises_path.exists():
            raise FileNotFoundError(f"운동 파일을 찾을 수 없습니다: {exercises_path}")

        with open(exercises_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        # exercises 키가 있으면 그 안의 데이터 사용
        exercises_data = raw_data.get("exercises", raw_data)

        # Dict → List 변환
        exercises_list = []
        for ex_id, ex_data in exercises_data.items():
            if ex_id.startswith("_"):  # _metadata 등 제외
                continue
            ex_data["id"] = ex_id
            exercises_list.append(ex_data)

        self._exercise_cache[body_part] = exercises_list
        return exercises_list

    def filter_for_bucket(
        self,
        body_part: str,
        bucket: str,
        physical_score: PhysicalScore,
        nrs: int,
        adjustments: Optional[DifficultyAdjustment] = None,
    ) -> Tuple[List[Dict], List[ExcludedExercise]]:
        """
        버킷 및 조건에 맞는 운동 필터링

        Args:
            body_part: 부위 코드
            bucket: 진단 버킷
            physical_score: 신체 점수
            nrs: 통증 점수
            adjustments: 난이도 조정 (사후 설문 기반)

        Returns:
            (후보 운동 리스트, 제외된 운동 리스트)
        """
        all_exercises = self._load_exercises(body_part)
        allowed_difficulties = self._get_allowed_difficulties(
            physical_score, nrs, adjustments
        )

        candidates = []
        excluded = []

        for ex in all_exercises:
            diagnosis_tags = ex.get("diagnosis_tags", [])

            # 버킷 매칭 체크
            if bucket not in diagnosis_tags:
                continue

            difficulty = ex.get("difficulty", "medium")

            # 난이도 체크
            if difficulty not in allowed_difficulties:
                excluded.append(
                    ExcludedExercise(
                        exercise_id=ex["id"],
                        name_kr=ex.get("name_kr", ex.get("name_en", "")),
                        reason=f"난이도 '{difficulty}'는 현재 조건에 부적합",
                        exclusion_type="difficulty" if nrs <= 4 else "nrs",
                    )
                )
                continue

            candidates.append(ex)

        return candidates, excluded

    def _get_allowed_difficulties(
        self,
        physical_score: PhysicalScore,
        nrs: int,
        adjustments: Optional[DifficultyAdjustment] = None,
    ) -> List[str]:
        """허용된 난이도 레벨 반환"""
        base_difficulties = physical_score.allowed_difficulties.copy()

        # NRS 기반 제한
        if nrs >= 7:
            base_difficulties = ["low"]
        elif nrs >= 4:
            base_difficulties = [d for d in base_difficulties if d != "high"]

        # 사후 설문 조정 적용
        if adjustments and adjustments.difficulty_delta != 0:
            all_levels = ["low", "medium", "high"]
            current_max_idx = max(
                all_levels.index(d) for d in base_difficulties
            )

            new_max_idx = min(
                max(0, current_max_idx + adjustments.difficulty_delta),
                len(all_levels) - 1,
            )

            # 조정된 범위
            base_difficulties = all_levels[: new_max_idx + 1]

        return base_difficulties

    def get_exercises_by_function(
        self,
        exercises: List[Dict],
    ) -> Dict[str, List[Dict]]:
        """기능별 운동 그룹화"""
        groups = {}
        for ex in exercises:
            for func in ex.get("function_tags", []):
                if func not in groups:
                    groups[func] = []
                groups[func].append(ex)
        return groups

    def apply_adjustments(
        self,
        exercise: Dict,
        adjustments: Optional[DifficultyAdjustment],
    ) -> Dict:
        """운동에 난이도 조정 적용"""
        if not adjustments or not adjustments.has_changes:
            return exercise

        adjusted = exercise.copy()

        # 세트 수 조정
        if adjustments.sets_delta != 0:
            current_sets = exercise.get("sets", 2)
            adjusted["sets"] = max(1, current_sets + adjustments.sets_delta)

        # 반복 횟수 조정
        if adjustments.reps_delta != 0:
            reps_str = exercise.get("reps", "10회")
            current_reps = self._parse_reps(reps_str)
            new_reps = max(5, current_reps + adjustments.reps_delta)
            adjusted["reps"] = f"{new_reps}회"

        # 휴식 시간 조정
        if adjustments.rest_delta != 0:
            rest_str = exercise.get("rest", "30초")
            current_rest = self._parse_rest(rest_str)
            new_rest = max(15, current_rest + adjustments.rest_delta)
            adjusted["rest"] = f"{new_rest}초"

        return adjusted

    def _parse_reps(self, reps_str: str) -> int:
        """반복 횟수 파싱"""
        import re
        match = re.search(r"(\d+)", reps_str)
        return int(match.group(1)) if match else 10

    def _parse_rest(self, rest_str: str) -> int:
        """휴식 시간 파싱"""
        import re
        match = re.search(r"(\d+)", rest_str)
        return int(match.group(1)) if match else 30
