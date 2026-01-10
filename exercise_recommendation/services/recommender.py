"""LLM 운동 추천 서비스"""

from typing import List, Dict, Optional, Any, TYPE_CHECKING
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

    @traceable(name="exercise_recommendation_flow")
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
        # Step 1: 프롬프트 구성
        prompt = self._build_prompt(candidates, user_input, adjustments)

        # Step 2: 후보 운동 분석
        candidate_analysis = self._analyze_candidates(candidates, user_input)

        # Step 3: LLM 호출
        result = self._call_llm(prompt)

        # Step 4: 응답 파싱 및 운동 매칭
        recommendations = self._parse_recommendations(result, candidates)

        # Step 5: 추론 포맷팅
        llm_reasoning = self._format_reasoning(result)

        return recommendations, llm_reasoning

    @traceable(name="candidate_analysis")
    def _analyze_candidates(
        self,
        candidates: List[Dict],
        user_input: ExerciseRecommendationInput,
    ) -> Dict:
        """후보 운동 분석"""
        analysis = {
            "total_candidates": len(candidates),
            "by_difficulty": {},
            "by_function": {},
            "patient_constraints": {
                "physical_level": user_input.physical_score.level,
                "nrs": user_input.nrs,
                "age": user_input.demographics.age,
            },
        }

        # 난이도별 분류
        for ex in candidates:
            diff = ex.get("difficulty", "medium")
            analysis["by_difficulty"][diff] = analysis["by_difficulty"].get(diff, 0) + 1

            # 기능별 분류
            for func in ex.get("function_tags", []):
                analysis["by_function"][func] = analysis["by_function"].get(func, 0) + 1

        return analysis

    @traceable(run_type="llm", name="llm_exercise_selection")
    def _call_llm(self, prompt: str) -> Dict:
        """LLM 호출"""
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

        return json.loads(response.choices[0].message.content)

    @traceable(name="recommendation_parsing")
    def _parse_recommendations(
        self,
        result: Dict,
        candidates: List[Dict],
    ) -> List[RecommendedExercise]:
        """LLM 응답 파싱 및 운동 매칭"""
        recommendations = []
        selected_ids = result.get("selected_exercises", [])

        for i, ex_id in enumerate(selected_ids):
            exercise = next(
                (c for c in candidates if c.get("id") == ex_id), None
            )
            if exercise:
                # LLM 이유가 없으면 기본 템플릿으로 보강
                reason = result.get("reasons", {}).get(ex_id)
                if not reason:
                    fn = ", ".join(exercise.get("function_tags", [])[:2]) or "기능 운동"
                    diff = exercise.get("difficulty", "medium")
                    reason = f"{exercise.get('name_kr', '')}: {fn}에 좋고 현재 난이도({diff})에서 무릎 통증을 악화시키지 않아 권장"
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

        return recommendations

    def _build_prompt(
        self,
        candidates: List[Dict],
        user_input: ExerciseRecommendationInput,
        adjustments: Optional[DifficultyAdjustment],
    ) -> str:
        """LLM 프롬프트 구성 - 개인화 강화 버전"""
        demo = user_input.demographics
        physical = user_input.physical_score

        # 후보 운동 목록 (상세 정보 포함)
        candidates_str = "\n".join(
            f"- {e['id']}: {e.get('name_kr', e.get('name_en', ''))} "
            f"(난이도: {e.get('difficulty', 'medium')}, "
            f"기능: {', '.join(e.get('function_tags', []))}, "
            f"대상근육: {', '.join(e.get('target_muscles', [])[:2])})"
            for e in candidates
        )

        # 환자 특성 분석
        patient_profile = self._analyze_patient_profile(demo, user_input.nrs, physical)

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

        # 건너뛴/즐겨찾기 운동 정보
        preference_str = ""
        if user_input.skipped_exercises:
            preference_str += f"\n- 자주 건너뛴 운동: {', '.join(user_input.skipped_exercises[:5])}"
        if user_input.favorite_exercises:
            preference_str += f"\n- 즐겨찾기 운동: {', '.join(user_input.favorite_exercises[:5])}"

        prompt = f"""
## 환자 정보
- 나이: {demo.age}세
- 성별: {demo.sex}
- BMI: {demo.bmi:.1f}
- 신체 점수: Lv {physical.level} ({physical.total_score}점)
- 통증 점수 (NRS): {user_input.nrs}/10

## 환자 특성 분석 (개인화 필수 반영)
{patient_profile}
{preference_str}

## 진단 버킷
{user_input.bucket}
{adjustment_str}
{assessment_str}

## 후보 운동 ({len(candidates)}개)
{candidates_str}

## 선택 기준 (중요도 순)
1. **환자 특성 맞춤**: 나이/BMI/통증에 따른 운동 강도 조절
2. **기능 균형**: 가동성, 근력, 안정성 운동을 균형 있게 포함
3. **다양성**: 같은 기능의 운동만 선택하지 말고 다양하게 선택
4. **진행성**: 쉬운 운동 → 어려운 운동 순서로 배치

## 개인화 가이드
- 고령자(65+): 균형/안정성 운동 우선, 고강도 제외
- 비만(BMI 30+): 체중 부하 적은 운동 우선
- 고통증(NRS 7+): 저강도, 가동성 위주
- 젊은 층(40-): 근력 운동 비중 높게

## reason 작성 규칙
- 각 운동마다 1~2문장으로 작성
- 포함 필수: (a) 어떤 기능/근육을 강화하는지, (b) 통증/나이/BMI/버킷(OA/OVR/TRM/INF/대상 부위)에 왜 맞는지, (c) 안전성/강도 배려 한 줄
- 예시: "브리지: 둔근/햄스트링 강화로 무릎 안정성에 도움, OA 환자이며 NRS 5로 저충격 코어 운동이 적합"

## 요청
환자에게 **최적화된** 운동 {settings.min_exercises}~{settings.max_exercises}개를 선택하세요.
반드시 환자 특성을 고려하여 **개인화된** 조합을 구성하세요.

다음 JSON 형식으로 응답하세요:
{{
    "selected_exercises": ["E01", "E02", ...],
    "reasons": {{
        "E01": "이 환자에게 추천하는 구체적 이유",
        "E02": "이 환자에게 추천하는 구체적 이유"
    }},
    "scores": {{
        "E01": 0.95,
        "E02": 0.90
    }},
    "combination_rationale": {{
        "why_together": "이 운동들의 시너지 효과",
        "bucket_coverage": "{user_input.bucket} 치료에 적합한 이유",
        "progression_logic": "순서 배치 논리"
    }},
    "patient_fit": {{
        "age_consideration": "나이({demo.age}세) 고려 내용",
        "bmi_consideration": "BMI({demo.bmi:.1f}) 고려 내용",
        "nrs_consideration": "통증({user_input.nrs}/10) 고려 내용",
        "physical_level_fit": "신체 Lv {physical.level} 적합성"
    }},
    "reasoning": "전체 추천 요약 (2-3문장)"
}}
"""
        return prompt

    def _analyze_patient_profile(
        self,
        demo: Any,
        nrs: int,
        physical: Any,
    ) -> str:
        """환자 프로필 분석 - LLM 프롬프트용"""
        profile_notes = []

        # 나이 기반 분석
        if demo.age >= 70:
            profile_notes.append("- **고령 환자**: 낙상 위험 고려, 균형/안정성 운동 필수, 고강도 운동 제외")
        elif demo.age >= 60:
            profile_notes.append("- **노년기**: 관절 보호 중요, 중등도 이하 난이도 권장")
        elif demo.age >= 50:
            profile_notes.append("- **중년기**: 근력 유지 중요, 적절한 강도 가능")
        elif demo.age < 35:
            profile_notes.append("- **젊은 연령**: 근력 강화 운동 적극 권장")

        # BMI 기반 분석
        bmi = demo.bmi
        if bmi >= 35:
            profile_notes.append("- **고도비만**: 체중 부하 최소화, 의자/누운 자세 운동 우선")
        elif bmi >= 30:
            profile_notes.append("- **비만**: 관절 부담 고려, 저충격 운동 선택")
        elif bmi >= 25:
            profile_notes.append("- **과체중**: 체중 관리와 근력 운동 병행")
        elif bmi < 18.5:
            profile_notes.append("- **저체중**: 근력 강화 집중")

        # 통증 기반 분석
        if nrs >= 7:
            profile_notes.append("- **심한 통증**: 저강도 가동성 운동만, 근력 운동 최소화")
        elif nrs >= 5:
            profile_notes.append("- **중등도 통증**: 통증 유발 동작 회피, 점진적 강화")
        elif nrs >= 3:
            profile_notes.append("- **경미한 통증**: 대부분 운동 가능, 주의하며 진행")
        else:
            profile_notes.append("- **통증 없음**: 적극적인 재활 운동 가능")

        # 신체 점수 기반
        level = physical.level
        if level == "D":
            profile_notes.append("- **신체 Lv D**: 기초 운동만, 저강도 위주")
        elif level == "C":
            profile_notes.append("- **신체 Lv C**: 기초~중급 운동 가능")
        elif level == "B":
            profile_notes.append("- **신체 Lv B**: 중급 운동 가능, 점진적 강화")
        else:  # A
            profile_notes.append("- **신체 Lv A**: 고급 운동 가능, 다양한 운동 선택")

        return "\n".join(profile_notes)

    def _format_reasoning(self, result: Dict) -> str:
        """추론 결과 포맷팅 - 개인화 정보 강화"""
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

        # 환자 적합성 추가 (개인화 정보 강화)
        fit = result.get("patient_fit", {})
        if fit:
            reasoning += "\n\n### 환자 맞춤 고려사항:\n"
            if fit.get("age_consideration"):
                reasoning += f"- **나이 고려**: {fit['age_consideration']}\n"
            if fit.get("bmi_consideration"):
                reasoning += f"- **BMI 고려**: {fit['bmi_consideration']}\n"
            if fit.get("nrs_consideration"):
                reasoning += f"- **통증 고려**: {fit['nrs_consideration']}\n"
            if fit.get("physical_level_fit"):
                reasoning += f"- **신체 수준**: {fit['physical_level_fit']}\n"
            # 이전 버전 호환성
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
