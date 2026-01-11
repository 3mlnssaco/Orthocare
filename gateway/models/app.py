"""App-facing request models for Gateway endpoints."""

from datetime import date
from typing import Optional, Literal, List, Union, Dict, Any

from pydantic import BaseModel, Field, ConfigDict, field_validator


class AppDiagnoseRequest(BaseModel):
    """앱 버킷 추론 요청 스키마 (요구 필드만 노출)"""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "additionalProperties": False,
            "example": {
                "birthDate": "2000-01-01",
                "height": 170,
                "weight": 65,
                "gender": "FEMALE",
                "painArea": "무릎",
                "affectedSide": "양쪽",
                "painStartedDate": "무리하게 운동한 이후부터 아파요",
                "painLevel": 6,
                "painTrigger": "계단 내려갈 때",
                "painSensation": "뻐근함",
                "painDuration": "30분 이상",
                "redFlags": ""
            }
        },
    )

    birth_date: date = Field(..., alias="birthDate", description="생년월일 (YYYY-MM-DD)")
    height: int = Field(..., description="키 (cm)")
    weight: int = Field(..., description="몸무게 (kg)")
    gender: Literal["MALE", "FEMALE", "PREFER_NOT_TO_SAY"] = Field(
        ...,
        description="성별 (서버 입력은 MALE/FEMALE/PREFER_NOT_TO_SAY, 화면 표기는 앱에서 한글 매핑)",
    )

    pain_area: str = Field(..., alias="painArea", description="통증 부위")
    affected_side: str = Field(..., alias="affectedSide", description="아픈 쪽")
    pain_started_date: str = Field(
        ...,
        alias="painStartedDate",
        description="언제부터 아팠는지 (날짜가 아닌 서술형 문자열)",
    )
    pain_level: int = Field(..., alias="painLevel", ge=0, le=10, description="통증 정도 (0-10)")
    pain_trigger: str = Field(..., alias="painTrigger", description="언제 통증이 더 심해지는지")
    pain_sensation: str = Field(..., alias="painSensation", description="어떤 느낌으로 아픈지")
    pain_duration: str = Field(..., alias="painDuration", description="통증 지속 시간")
    red_flags: str = Field(..., alias="redFlags", description="위험 신호")


class AppDiagnoseResponse(BaseModel):
    """앱 버킷 추론 응답 스키마 (요약 필드만 노출)"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "diagnosisPercentage": 72,
                "diagnosisType": "OA",
                "diagnosisDescription": "무릎 연골 약화로 통증이 점진적으로 나타나는 패턴",
            }
        },
    )

    diagnosis_percentage: int = Field(..., alias="diagnosisPercentage", description="진단 확률 (0-100)")
    diagnosis_type: str = Field(
        ..., alias="diagnosisType", description="진단 유형 (버킷 코드: OA/OVR/TRM/INF/STF)"
    )
    diagnosis_description: str = Field(
        ..., alias="diagnosisDescription", description="진단 설명 (사용자용)"
    )

class AppPostSurvey(BaseModel):
    """사후 설문 (운동 후 피드백)"""

    rpe_response: Optional[str] = Field(
        default=None, alias="rpeResponse", description="운동 끝난 후 몸은 어떠한가요?"
    )
    muscle_stimulation_response: Optional[str] = Field(
        default=None,
        alias="muscleStimulationResponse",
        description="오늘 내 근육은 어떻게 느꼈나요?",
    )
    sweat_response: Optional[str] = Field(
        default=None, alias="sweatResponse", description="운동 중 땀은 어느정도 났나요?"
    )


class AppExerciseRequest(BaseModel):
    """앱 운동 추천 요청 스키마 (요구 필드만 노출)"""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "example": {
                "userId": 1,
                "routineDate": "2025-01-11",
                "painLevel": 5,
                "squatResponse": "10개",
                "pushupResponse": "5개",
                "stepupResponse": "15개",
                "plankResponse": "30초",
                "postSurvey": {
                    "rpeResponse": "적당함",
                    "muscleStimulationResponse": "중간",
                    "sweatResponse": "보통"
                },
                "bucket": "OA",
                "bodyPart": "knee",
                "age": 26,
                "gender": "FEMALE",
                "height": 170,
                "weight": 65,
                "physicalScore": 12
            }
        },
    )

    user_id: int = Field(..., alias="userId", description="유저 ID (number)")
    routine_date: date = Field(..., alias="routineDate", description="루틴 날짜 (YYYY-MM-DD)")
    pain_level: int = Field(..., alias="painLevel", ge=0, le=10, description="일일 통증 정도 (0-10)")
    squat_response: str = Field(..., alias="squatResponse", description="스쿼트 가능 횟수")
    pushup_response: str = Field(..., alias="pushupResponse", description="푸시업 가능 횟수")
    stepup_response: str = Field(..., alias="stepupResponse", description="스텝업 가능 횟수")
    plank_response: str = Field(
        ...,
        alias="plankResponse",
        description="플랭크 유지 시간 (예: 30초)",
    )

    # 백엔드에서 추가로 전달 (필수)
    physical_score: Optional[int] = Field(
        default=None,
        alias="physicalScore",
        description="(백엔드) 신체 점수 (4-16)",
    )
    post_survey: Optional[AppPostSurvey] = Field(
        default=None,
        alias="postSurvey",
        description="(사후) 운동 후 피드백",
    )
    bucket: Optional[str] = Field(
        default=None,
        description="(백엔드) 진단 버킷 코드 (OA/OVR/TRM/INF/STF) 또는 diagnosisType",
    )
    diagnosis_type: Optional[str] = Field(
        default=None,
        alias="diagnosisType",
        description="(백엔드) 진단 유형 텍스트 (퇴행성형/과사용형/외상형/염증형/경직형)",
    )
    body_part: Optional[str] = Field(
        default=None,
        alias="bodyPart",
        description="(백엔드) 부위 코드 (knee/shoulder/back/neck/ankle)",
    )
    pain_area: Optional[str] = Field(
        default=None,
        alias="painArea",
        description="(백엔드) 통증 부위 (한글 가능: 무릎/어깨/허리/목/발목)",
    )
    demographics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="(백엔드) 인구통계 {age, sex(male/female/prefer_not_to_say), height_cm, weight_kg}",
    )
    age: Optional[int] = Field(default=None, description="(백엔드) 나이 (birthDate 대신 사용)")
    gender: Optional[str] = Field(
        default=None,
        description="(백엔드) 성별 (MALE/FEMALE/PREFER_NOT_TO_SAY 또는 male/female)",
    )
    height: Optional[int] = Field(default=None, description="(백엔드) 키 (cm)")
    weight: Optional[int] = Field(default=None, description="(백엔드) 몸무게 (kg)")
    birth_date: Optional[date] = Field(
        default=None, alias="birthDate", description="(백엔드) 생년월일 (YYYY-MM-DD)"
    )

    @field_validator("physical_score", mode="before")
    @classmethod
    def normalize_physical_score(cls, value):
        if value is None:
            return value
        if isinstance(value, dict):
            total = value.get("totalScore") or value.get("total_score")
            return int(total) if total is not None else None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class AppExerciseItem(BaseModel):
    """앱 운동 추천 응답 아이템"""

    exercise_id: str = Field(..., alias="exerciseId")
    name_ko: str = Field(..., alias="nameKo")
    difficulty: str
    recommended_sets: int = Field(..., alias="recommendedSets")
    recommended_reps: int = Field(..., alias="recommendedReps")
    exercise_order: int = Field(..., alias="exerciseOrder")
    video_url: Optional[str] = Field(default=None, alias="videoUrl")


class AppExerciseResponse(BaseModel):
    """앱 운동 추천 응답 스키마"""

    user_id: int = Field(..., alias="userId")
    routine_date: date = Field(..., alias="routineDate")
    physical_score: Optional[int] = Field(
        default=None,
        alias="physicalScore",
        description="신체 점수 (4-16)",
    )
    exercises: List[AppExerciseItem]

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "example": {
                "userId": 1,
                "routineDate": "2025-01-11",
                "physicalScore": 12,
                "exercises": [
                    {
                        "exerciseId": "EX001",
                        "nameKo": "무릎 스트레칭",
                        "difficulty": "기초 단계",
                        "recommendedSets": 3,
                        "recommendedReps": 10,
                        "exerciseOrder": 1,
                        "videoUrl": "https://..."
                    },
                    {
                        "exerciseId": "EX002",
                        "nameKo": "레그 레이즈",
                        "difficulty": "중급",
                        "recommendedSets": 3,
                        "recommendedReps": 12,
                        "exerciseOrder": 2,
                        "videoUrl": "https://…"
                    }
                ]
            }
        },
    )
