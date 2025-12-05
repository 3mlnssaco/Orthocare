#!/usr/bin/env python3
"""OrthoCare V3 E2E 테스트

V3 마이크로서비스 아키텍처 테스트:
- Bucket Inference API (8001)
- Exercise Recommendation API (8002)

실행:
    python scripts/test_e2e_v3.py
    python scripts/test_e2e_v3.py --all
"""

import sys
import json
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# 프로젝트 루트
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# API 엔드포인트
BUCKET_API = "http://localhost:8001"
EXERCISE_API = "http://localhost:8002"

# 데이터 경로
DATA_DIR = project_root / "data"


class Colors:
    """터미널 색상"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(title: str):
    """섹션 헤더"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD} {title}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")


def print_step(msg: str, status: str = ""):
    """단계 출력"""
    if status == "OK" or status == "PASS":
        icon = f"{Colors.GREEN}✓{Colors.END}"
    elif status == "FAIL":
        icon = f"{Colors.RED}✗{Colors.END}"
    elif status == "WARN":
        icon = f"{Colors.YELLOW}!{Colors.END}"
    else:
        icon = "→"
    print(f"  {icon} {msg}")


def load_personas() -> List[Dict]:
    """페르소나 데이터 로드"""
    persona_file = DATA_DIR / "evaluation" / "golden_set" / "knee_personas.json"
    if not persona_file.exists():
        print_step(f"페르소나 파일 없음: {persona_file}", "WARN")
        return get_default_personas()

    with open(persona_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("personas", [])


def get_default_personas() -> List[Dict]:
    """기본 테스트 페르소나"""
    return [
        {
            "id": "TEST-OA-001",
            "name": "55세 남성 무릎 퇴행성 관절염",
            "input": {
                "demographics": {"age": 55, "sex": "male", "height_cm": 175, "weight_kg": 80},
                "body_parts": [{"code": "knee", "symptoms": ["pain_stairs", "stiffness_morning"], "nrs": 6}],
            },
            "expected": {"bucket": "OA"}
        },
        {
            "id": "TEST-TRM-001",
            "name": "28세 남성 ACL 손상",
            "input": {
                "demographics": {"age": 28, "sex": "male", "height_cm": 180, "weight_kg": 75},
                "body_parts": [{"code": "knee", "symptoms": ["instability", "swelling_acute", "trauma_recent"], "nrs": 7}],
            },
            "expected": {"bucket": "TRM"}
        },
        {
            "id": "TEST-OVR-001",
            "name": "35세 여성 슬개대퇴 증후군",
            "input": {
                "demographics": {"age": 35, "sex": "female", "height_cm": 165, "weight_kg": 58},
                "body_parts": [{"code": "knee", "symptoms": ["pain_anterior", "pain_prolonged_sitting", "crepitus"], "nrs": 5}],
            },
            "expected": {"bucket": "OVR"}
        },
    ]


def test_health_check() -> bool:
    """서비스 헬스 체크"""
    print_header("1. 서비스 헬스 체크")

    all_ok = True

    # Bucket Inference
    try:
        resp = requests.get(f"{BUCKET_API}/health", timeout=5)
        if resp.status_code == 200:
            print_step(f"Bucket Inference (8001): {resp.json()['status']}", "OK")
        else:
            print_step(f"Bucket Inference (8001): HTTP {resp.status_code}", "FAIL")
            all_ok = False
    except Exception as e:
        print_step(f"Bucket Inference (8001): {e}", "FAIL")
        all_ok = False

    # Exercise Recommendation
    try:
        resp = requests.get(f"{EXERCISE_API}/health", timeout=5)
        if resp.status_code == 200:
            print_step(f"Exercise Recommendation (8002): {resp.json()['status']}", "OK")
        else:
            print_step(f"Exercise Recommendation (8002): HTTP {resp.status_code}", "FAIL")
            all_ok = False
    except Exception as e:
        print_step(f"Exercise Recommendation (8002): {e}", "FAIL")
        all_ok = False

    return all_ok


def test_bucket_inference(persona: Dict) -> Dict:
    """버킷 추론 테스트"""
    result = {
        "service": "bucket_inference",
        "success": False,
        "expected_bucket": persona["expected"]["bucket"],
        "actual_bucket": None,
        "confidence": None,
        "error": None,
        "response_time_ms": None,
    }

    try:
        start = datetime.now()
        resp = requests.post(
            f"{BUCKET_API}/api/v1/infer-bucket",
            json=persona["input"],
            timeout=60,
        )
        elapsed = (datetime.now() - start).total_seconds() * 1000
        result["response_time_ms"] = round(elapsed)

        if resp.status_code == 200:
            data = resp.json()
            result["actual_bucket"] = data.get("final_bucket")
            result["confidence"] = data.get("confidence")
            result["weight_ranking"] = data.get("weight_ranking")
            result["search_ranking"] = data.get("search_ranking")
            result["llm_reasoning"] = data.get("llm_reasoning", "")[:500]
            result["evidence_summary"] = data.get("evidence_summary", "")

            # 성공 여부 판단
            if result["actual_bucket"] == result["expected_bucket"]:
                result["success"] = True
        else:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"

    except Exception as e:
        result["error"] = str(e)

    return result


def test_exercise_recommendation(persona: Dict, bucket: str) -> Dict:
    """운동 추천 테스트"""
    result = {
        "service": "exercise_recommendation",
        "success": False,
        "exercise_count": 0,
        "exercises": [],
        "error": None,
        "response_time_ms": None,
    }

    # 운동 추천 입력 구성
    input_data = {
        "user_id": f"test-{persona['id']}",
        "body_part": persona["input"]["body_parts"][0]["code"],
        "bucket": bucket,
        "physical_score": {"total_score": 12},  # Lv B
        "demographics": persona["input"]["demographics"],
        "nrs": persona["input"]["body_parts"][0].get("nrs", 5),
    }

    try:
        start = datetime.now()
        resp = requests.post(
            f"{EXERCISE_API}/api/v1/recommend-exercises",
            json=input_data,
            timeout=60,
        )
        elapsed = (datetime.now() - start).total_seconds() * 1000
        result["response_time_ms"] = round(elapsed)

        if resp.status_code == 200:
            data = resp.json()
            exercises = data.get("exercises", [])
            result["exercise_count"] = len(exercises)
            result["exercises"] = [
                {"name": ex.get("name_kr"), "reason": ex.get("reason", "")[:50]}
                for ex in exercises[:5]
            ]
            result["assessment_status"] = data.get("assessment_status")
            result["llm_reasoning"] = data.get("llm_reasoning", "")[:500]

            # 성공 여부: 운동이 4개 이상 추천되면 성공
            if len(exercises) >= 4:
                result["success"] = True
        else:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"

    except Exception as e:
        result["error"] = str(e)

    return result


def run_persona_test(persona: Dict) -> Dict:
    """페르소나별 전체 테스트"""
    print(f"\n{Colors.BLUE}{'─'*60}{Colors.END}")
    print(f"{Colors.BOLD}테스트: {persona['id']} - {persona['name']}{Colors.END}")
    print(f"예상 버킷: {persona['expected']['bucket']}")

    results = {
        "persona_id": persona["id"],
        "persona_name": persona["name"],
        "bucket_inference": None,
        "exercise_recommendation": None,
        "overall_success": False,
    }

    # 1. 버킷 추론
    print_step("버킷 추론 실행 중...")
    bucket_result = test_bucket_inference(persona)
    results["bucket_inference"] = bucket_result

    if bucket_result["success"]:
        print_step(f"버킷: {bucket_result['actual_bucket']} (신뢰도: {bucket_result['confidence']:.2f})", "PASS")
    elif bucket_result["actual_bucket"]:
        print_step(f"버킷: {bucket_result['actual_bucket']} (예상: {bucket_result['expected_bucket']})", "FAIL")
    else:
        print_step(f"버킷 추론 실패: {bucket_result['error']}", "FAIL")

    print_step(f"응답 시간: {bucket_result['response_time_ms']}ms")

    # 2. 운동 추천 (버킷 추론 성공 시)
    actual_bucket = bucket_result.get("actual_bucket") or persona["expected"]["bucket"]
    print_step(f"운동 추천 실행 중 (버킷: {actual_bucket})...")

    exercise_result = test_exercise_recommendation(persona, actual_bucket)
    results["exercise_recommendation"] = exercise_result

    if exercise_result["success"]:
        print_step(f"운동 {exercise_result['exercise_count']}개 추천됨", "PASS")
        for ex in exercise_result["exercises"][:3]:
            print(f"      - {ex['name']}")
    else:
        print_step(f"운동 추천 실패: {exercise_result.get('error', 'unknown')}", "FAIL")

    print_step(f"응답 시간: {exercise_result['response_time_ms']}ms")

    # 전체 성공 여부
    results["overall_success"] = bucket_result["success"] and exercise_result["success"]

    return results


def run_tests(persona_id: Optional[str] = None, run_all: bool = False):
    """테스트 실행"""
    print_header("OrthoCare V3 E2E 테스트")
    print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 헬스 체크
    if not test_health_check():
        print(f"\n{Colors.RED}서비스가 실행 중이 아닙니다. 테스트를 종료합니다.{Colors.END}")
        print("서비스 시작 방법:")
        print("  PYTHONPATH=. python -m bucket_inference.main &")
        print("  PYTHONPATH=. python -m exercise_recommendation.main &")
        return

    # 페르소나 로드
    personas = load_personas()
    print_step(f"페르소나 로드: {len(personas)}개")

    # 테스트 대상 선택
    if persona_id:
        test_personas = [p for p in personas if p["id"] == persona_id]
        if not test_personas:
            print(f"\n페르소나 '{persona_id}'를 찾을 수 없습니다.")
            return
    elif run_all:
        test_personas = personas
    else:
        test_personas = personas[:3]  # 기본: 상위 3개

    # 테스트 실행
    all_results = []
    for persona in test_personas:
        result = run_persona_test(persona)
        all_results.append(result)

    # 결과 요약
    print_header("테스트 결과 요약")

    passed = sum(1 for r in all_results if r["overall_success"])
    bucket_passed = sum(1 for r in all_results if r["bucket_inference"]["success"])
    exercise_passed = sum(1 for r in all_results if r["exercise_recommendation"]["success"])
    total = len(all_results)

    print(f"\n{Colors.BOLD}전체 성공률: {passed}/{total} ({passed/total*100:.0f}%){Colors.END}")
    print(f"  - 버킷 추론: {bucket_passed}/{total}")
    print(f"  - 운동 추천: {exercise_passed}/{total}")

    print(f"\n{Colors.BOLD}건별 결과:{Colors.END}")
    for r in all_results:
        bucket = r["bucket_inference"]
        exercise = r["exercise_recommendation"]

        status = f"{Colors.GREEN}PASS{Colors.END}" if r["overall_success"] else f"{Colors.RED}FAIL{Colors.END}"
        bucket_status = "✓" if bucket["success"] else "✗"
        exercise_status = "✓" if exercise["success"] else "✗"

        print(f"  [{status}] {r['persona_id']}")
        print(f"       버킷 {bucket_status}: {bucket.get('actual_bucket', 'N/A')} (예상: {bucket['expected_bucket']})")
        print(f"       운동 {exercise_status}: {exercise['exercise_count']}개")

    # 결과 저장
    results_dir = DATA_DIR / "evaluation" / "test_results" / datetime.now().strftime("%Y-%m-%d")
    results_dir.mkdir(parents=True, exist_ok=True)

    result_file = results_dir / f"v3_e2e_{datetime.now().strftime('%H%M%S')}.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n결과 저장: {result_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OrthoCare V3 E2E 테스트")
    parser.add_argument("--persona", "-p", help="특정 페르소나 ID")
    parser.add_argument("--all", "-a", action="store_true", help="모든 페르소나 테스트")

    args = parser.parse_args()
    run_tests(persona_id=args.persona, run_all=args.all)
