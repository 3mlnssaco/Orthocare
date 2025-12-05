"""LLM 운동 추천 서비스"""

from typing import List, Dict, Optional, Any
import json

from openai import OpenAI
from langsmith import traceable

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from exercise_recommendation.models.input import ExerciseRecommendationInput
from exercise_recommendation.models.output import RecommendedExercise
from exercise_recommendation.models.assessment import DifficultyAdjustment
from exercise_recommendation.config import settings


class ExerciseRecommender:
    """LLM 기반 운동 추천 서비스"""

    def __init__(self, openai_client: Optional[OpenAI] = None):
        """
        Args:
            openai_client: OpenAI 클라이언트
        """
        self._openai = openai_client or OpenAI()
        self._model = settings.openai_model

    @traceable(run_type="llm", name="llm_exercise_recommendation")
    def recommend(
        self,
        candidates: List[Dict],
        user_input: ExerciseRecommendationInput,
        adjustments: Optional[DifficultyAdjustment] = None,
    ) -> tuple:
        """
        LLM 운동 추천

        Args:
            candidates: 후보 운동 목록
            user_input: 사용자 입력
            adjustments: 난이도 조정

        Returns:
            (추천 운동 목록, LLM 추론)
        """
        prompt = self._build_prompt(candidates, user_input, adjustments)

        response = self._openai.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 재활 운동 전문가입니다. "
                        "환자의 상태와 사후 설문 결과를 반영하여 "
                        "최적의 운동 프로그램을 추천합니다. "
                        "반드시 JSON 형식으로 응답하세요."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )

        result = json.loads(response.choices[0].message.content)

        # 추천 결과 파싱
        recommendations = []
        selected_ids = result.get("selected_exercises", [])

        for i, ex_id in enumerate(selected_ids):
            exercise = next(
                (c for c in candidates if c.get("id") == ex_id), None
            )
            if exercise:
                reason = result.get("reasons", {}).get(ex_id, "추천됨")
                match_score = result.get("scores", {}).get(ex_id, 0.8)

                recommendations.append(
                    RecommendedExercise(
                        exercise_id=ex_id,
                        name_kr=exercise.get("name_kr", ""),
                        name_en=exercise.get("name_en", ""),
                        difficulty=exercise.get("difficulty", "medium"),
                        function_tags=exercise.get("function_tags", []),
                        target_muscles=exercise.get("target_muscles", []),
                        sets=exercise.get("sets", 2),
                        reps=exercise.get("reps", "10회"),
                        rest=exercise.get("rest", "30초"),
                        reason=reason,
                        priority=i + 1,
                        match_score=match_score,
                        youtube=exercise.get("youtube"),
                        description=exercise.get("description"),
                    )
                )

        # 전체 추론 구성
        llm_reasoning = self._format_reasoning(result)

        return recommendations, llm_reasoning

    def _build_prompt(
        self,
        candidates: List[Dict],
        user_input: ExerciseRecommendationInput,
        adjustments: Optional[DifficultyAdjustment],
    ) -> str:
        """LLM 프롬프트 구성"""
        demo = user_input.demographics
        physical = user_input.physical_score

        # 후보 운동 목록
        candidates_str = "\n".join(
            f"- {e['id']}: {e.get('name_kr', e.get('name_en', ''))} "
            f"(난이도: {e.get('difficulty', 'medium')}, "
            f"기능: {', '.join(e.get('function_tags', []))})"
            for e in candidates
        )

        # 조정 정보
        adjustment_str = ""
        if adjustments and adjustments.has_changes:
            adjustment_str = f"""
## 사후 설문 기반 조정
- 난이도 조정: {'+' if adjustments.difficulty_delta > 0 else ''}{adjustments.difficulty_delta}
- 세트 조정: {'+' if adjustments.sets_delta > 0 else ''}{adjustments.sets_delta}
- 반복 조정: {'+' if adjustments.reps_delta > 0 else ''}{adjustments.reps_delta}
"""

        # 사후 설문 이력
        assessment_str = ""
        if user_input.previous_assessments:
            recent = user_input.previous_assessments[-1]
            assessment_str = f"""
## 최근 사후 설문 (RPE)
- 난이도 체감: {recent.difficulty_felt}/5
- 근육 자극: {recent.muscle_stimulus}/5
- 땀 배출: {recent.sweat_level}/5
- 총점: {recent.total_rpe_score}/15
"""

        prompt = f"""
## 환자 정보
- 나이: {demo.age}세
- 성별: {demo.sex}
- BMI: {demo.bmi}
- 신체 점수: Lv {physical.level} ({physical.total_score}점)
- 통증 점수 (NRS): {user_input.nrs}/10

## 진단 버킷
{user_input.bucket}
{adjustment_str}
{assessment_str}

## 후보 운동
{candidates_str}

## 요청
환자에게 적합한 운동 {settings.min_exercises}~{settings.max_exercises}개를 선택하세요.
운동 순서: 가동성 → 근력 → 균형

다음 JSON 형식으로 응답하세요:
{{
    "selected_exercises": ["E01", "E02", ...],
    "reasons": {{
        "E01": "추천 이유",
        "E02": "추천 이유"
    }},
    "scores": {{
        "E01": 0.95,
        "E02": 0.90
    }},
    "combination_rationale": {{
        "why_together": "운동 조합 시너지",
        "bucket_coverage": "버킷 치료 적합성",
        "progression_logic": "순서 논리"
    }},
    "patient_fit": {{
        "physical_level_fit": "신체 점수 적합성",
        "nrs_consideration": "통증 고려",
        "assessment_reflection": "사후 설문 반영 (있다면)"
    }},
    "reasoning": "전체 요약"
}}
"""
        return prompt

    def _format_reasoning(self, result: Dict) -> str:
        """추론 결과 포맷팅"""
        reasoning = result.get("reasoning", "")

        # 조합 근거 추가
        combo = result.get("combination_rationale", {})
        if combo:
            reasoning += "\n\n### 운동 조합 근거:\n"
            if combo.get("why_together"):
                reasoning += f"- **시너지**: {combo['why_together']}\n"
            if combo.get("bucket_coverage"):
                reasoning += f"- **버킷 치료**: {combo['bucket_coverage']}\n"
            if combo.get("progression_logic"):
                reasoning += f"- **순서 논리**: {combo['progression_logic']}\n"

        # 환자 적합성 추가
        fit = result.get("patient_fit", {})
        if fit:
            reasoning += "\n\n### 환자 맞춤 고려사항:\n"
            if fit.get("physical_level_fit"):
                reasoning += f"- **신체 수준**: {fit['physical_level_fit']}\n"
            if fit.get("nrs_consideration"):
                reasoning += f"- **통증 고려**: {fit['nrs_consideration']}\n"
            if fit.get("assessment_reflection"):
                reasoning += f"- **사후 설문 반영**: {fit['assessment_reflection']}\n"

        return reasoning

    def simple_recommend(
        self,
        candidates: List[Dict],
        physical_level: str,
    ) -> List[RecommendedExercise]:
        """LLM 없이 간단한 추천"""
        max_count = {
            "A": 7,
            "B": 6,
            "C": 5,
            "D": 4,
        }.get(physical_level, 5)

        # 난이도 순 정렬
        difficulty_order = {"low": 0, "medium": 1, "high": 2}
        sorted_candidates = sorted(
            candidates,
            key=lambda x: difficulty_order.get(x.get("difficulty", "medium"), 1),
        )

        recommendations = []
        for i, ex in enumerate(sorted_candidates[:max_count]):
            recommendations.append(
                RecommendedExercise(
                    exercise_id=ex.get("id", f"E{i+1:02d}"),
                    name_kr=ex.get("name_kr", ""),
                    name_en=ex.get("name_en", ""),
                    difficulty=ex.get("difficulty", "medium"),
                    function_tags=ex.get("function_tags", []),
                    target_muscles=ex.get("target_muscles", []),
                    sets=ex.get("sets", 2),
                    reps=ex.get("reps", "10회"),
                    rest=ex.get("rest", "30초"),
                    reason=f"{ex.get('name_kr', '')}: {', '.join(ex.get('function_tags', []))}",
                    priority=i + 1,
                    match_score=0.8 - (i * 0.05),
                    youtube=ex.get("youtube"),
                    description=ex.get("description"),
                )
            )

        return recommendations
