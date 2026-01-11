"""App-facing request models for Gateway endpoints."""

from datetime import date
from typing import Optional, Literal, List, Union, Dict, Any

from pydantic import BaseModel, Field, ConfigDict


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
                "diagnosisType": "퇴행성형",
                "diagnosisDescription": "무릎 연골 약화로 통증이 점진적으로 나타나는 패턴",
                "tags": ["연골 약화", "계단·보행 시 통증", "근력·가동성 운동"],
            }
        },
    )

    diagnosis_percentage: int = Field(..., alias="diagnosisPercentage", description="진단 확률 (0-100)")
    diagnosis_type: str = Field(
        ..., alias="diagnosisType", description="진단 유형 (예: 퇴행성형/과사용형/외상형/염증형)"
    )
    diagnosis_description: str = Field(
        ..., alias="diagnosisDescription", description="진단 설명 (사용자용)"
    )
    tags: List[str] = Field(..., description="특징 태그 (최소 3개 권장)")


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
                "rpeResponse": "적당함",
                "muscleStimulationResponse": "중간",
                "sweatResponse": "보통",
                "bucket": "OA",
                "bodyPart": "knee",
                "age": 26,
                "gender": "FEMALE",
                "height": 170,
                "weight": 65
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

    rpe_response: Optional[str] = Field(
        ..., alias="rpeResponse", description="운동 끝난 후 몸은 어떠한가요? (null 허용)"
    )
    muscle_stimulation_response: Optional[str] = Field(
        ...,
        alias="muscleStimulationResponse",
        description="오늘 내 근육은 어떻게 느꼈나요? (null 허용)",
    )
    sweat_response: Optional[str] = Field(
        ..., alias="sweatResponse", description="운동 중 땀은 어느정도 났나요? (null 허용)"
    )

    # 백엔드에서 추가로 전달 (필수)
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
    exercises: List[AppExerciseItem]

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow",
        json_schema_extra={
            "example": {
                "userId": 1,
                "routineDate": "2025-01-11",
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
