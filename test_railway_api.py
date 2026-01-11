"""Railway 배포 API 테스트 스크립트

사용법:
    python test_railway_api.py <RAILWAY_URL>

예시:
    python test_railway_api.py https://your-app.railway.app
"""

import requests
import json
import sys
from typing import Dict, Any, Optional

def test_health_check(base_url: str) -> Dict[str, Any]:
    """헬스 체크"""
    url = f"{base_url}/health"
    
    try:
        response = requests.get(url, timeout=5)
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "response": response.json() if response.status_code == 200 else response.text,
            "error": None
        }
    except Exception as e:
        return {
            "status_code": None,
            "success": False,
            "response": None,
            "error": str(e)
        }


def test_exercise_only(base_url: str) -> Dict[str, Any]:
    """운동 추천만 테스트"""
    url = f"{base_url}/api/v1/recommend-exercises"
    
    # 운동 추천 입력 (버킷/인구통계 포함)
    payload = {
        "userId": 1,
        "routineDate": "2025-01-11",
        "painLevel": 5,
        "squatResponse": "10개",
        "pushupResponse": "5개",
        "stepupResponse": "15개",
        "plankResponse": "30초",
        "bucket": "OA",
        "bodyPart": "knee",
        "age": 26,
        "gender": "FEMALE",
        "height": 170,
        "weight": 65,
        "physicalScore": 70
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "response": response.json() if response.status_code == 200 else response.text,
            "error": None,
            "payload": payload
        }
    except Exception as e:
        return {
            "status_code": None,
            "success": False,
            "response": None,
            "error": str(e),
            "payload": payload
        }


def test_diagnose_only(base_url: str) -> Dict[str, Any]:
    """진단만 실행 (운동 추천 제외)"""
    url = f"{base_url}/api/v1/diagnose"
    
    payload = {
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
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "response": response.json() if response.status_code == 200 else response.text,
            "error": None,
            "payload": payload
        }
    except Exception as e:
        return {
            "status_code": None,
            "success": False,
            "response": None,
            "error": str(e),
            "payload": payload
        }


def main():
    if len(sys.argv) < 2:
        print("사용법: python test_railway_api.py <RAILWAY_URL>")
        print("예시: python test_railway_api.py https://your-app.railway.app")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    
    print("=" * 70)
    print("Railway 배포 API 테스트")
    print("=" * 70)
    print(f"\n대상 URL: {base_url}\n")
    
    # 헬스 체크
    print("1. 헬스 체크")
    print("-" * 70)
    health_result = test_health_check(base_url)
    print(json.dumps(health_result, indent=2, ensure_ascii=False))
    
    if not health_result["success"]:
        print("\n⚠️  헬스 체크 실패. URL을 확인하세요.")
        sys.exit(1)
    
    # 최소 요청 테스트
    print("\n\n2. 버킷 추론만 테스트 (/api/v1/diagnose)")
    print("-" * 70)
    diag_result = test_diagnose_only(base_url)
    print(json.dumps(diag_result.get("payload", {}), indent=2, ensure_ascii=False))
    print("\n📥 응답:")
    print(json.dumps({k: v for k, v in diag_result.items() if k != "payload"}, indent=2, ensure_ascii=False))
    
    # 운동 추천만 테스트
    print("\n\n3. 운동 추천만 테스트 (/api/v1/recommend-exercises)")
    print("-" * 70)
    print("📝 요청 페이로드:")
    ex_result = test_exercise_only(base_url)
    print(json.dumps(ex_result.get("payload", {}), indent=2, ensure_ascii=False))
    print("\n📥 응답:")
    print(json.dumps({k: v for k, v in ex_result.items() if k != "payload"}, indent=2, ensure_ascii=False))
    
    # 요약
    print("\n\n" + "=" * 70)
    print("테스트 요약")
    print("=" * 70)
    print(f"헬스 체크:        {'✅ 성공' if health_result['success'] else '❌ 실패'}")
    print(f"버킷 추론:        {'✅ 성공' if diag_result['success'] else '❌ 실패'}")
    print(f"운동 추천:        {'✅ 성공' if ex_result['success'] else '❌ 실패'}")
    
    # 실패한 테스트 상세 정보
    failures = []
    if not diag_result['success']:
        failures.append(("버킷 추론", diag_result))
    if not ex_result['success']:
        failures.append(("운동 추천", ex_result))
    
    if failures:
        print("\n\n❌ 실패한 테스트 상세:")
        print("-" * 70)
        for name, result in failures:
            print(f"\n{name}:")
            if result.get('error'):
                print(f"  에러: {result['error']}")
            if result.get('status_code'):
                print(f"  상태 코드: {result['status_code']}")
            if result.get('response'):
                print(f"  응답: {json.dumps(result['response'], indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
