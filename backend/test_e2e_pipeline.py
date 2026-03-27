import asyncio
import os
import sys
import glob
from PIL import Image

# 현재 디렉토리를 모듈 경로에 추가
sys.path.append(os.getcwd())

from app.services.gemini_service import gemini_service
from app.services.automation.naver_v2 import naver_automation_v2

def run_e2e_test():
    print("=" * 60)
    print("🚀 [E2E 통합 테스트] AI 분석부터 네이버 발행까지 전체 파이프라인 가동")
    print("=" * 60)
    
    # 1. 테스트용 이미지 찾기 (루트 폴더 또는 현재 폴더의 KakaoTalk 이미지 활용)
    found_images = glob.glob("..\\KakaoTalk_*.jpg") + glob.glob("KakaoTalk_*.jpg")
    if len(found_images) < 2:
        print("⚠️ 테스트를 위한 이미지가 부족합니다. (최소 2장 필요)")
        return
        
    # 메모리 절약을 위해 최대 3장까지만 사용
    image_paths = [os.path.abspath(img) for img in found_images[:3]] 
    pil_images = [Image.open(path) for path in image_paths]
    print(f"📸 1단계: 총 {len(image_paths)}장의 테스트 이미지가 준비되었습니다.")

    # 2. 가상의 사용자 입력 데이터 (프론트엔드에서 넘어오는 데이터 모사)
    initial_facts = {
        "place_name": "포스트플로우 통합테스트점",
        "address": "서울 강남구 테헤란로 123",
        "business_hours": "매일 11:00 - 21:00",
        "parking": "불가",
        "visitor_insight": "아주 훌륭한 시스템입니다!",
        "image_hints": ["매장 외관입니다", "내부분위기", "메인 요리"][:len(image_paths)]
    }

    # 3. AI 기사 작성 (Gemini 호출)
    print("\n🤖 2단계: Gemini AI 기사 작성 프로세스 진입...")
    try:
        ai_result = asyncio.run(gemini_service.analyze_images(
            images=pil_images,
            style="emotional",
            initial_facts=initial_facts
        ))
        print(f"  ✅ AI 원고 작성 성공!")
        print(f"  📝 [생성된 제목]: {ai_result.title}")
        print(f"  🧩 [블록 개수]: {len(ai_result.blocks)}개 생성됨")
    except Exception as e:
        print(f"❌ AI 분석 단계 실패: {e}")
        return

    # 4. 자동 발행 봇 호출 (Playwright)
    print("\n🤖 3단계: 네이버 자동 발행 봇(V2) 호출 중...")
    
    success = naver_automation_v2.publish(
        title=ai_result.title,
        blocks=ai_result.blocks, # AI가 만들어준 블록을 그대로 던짐!
        image_paths=image_paths,
        images_data=[],
        facts=initial_facts,
        max_retries=1  # E2E 테스트에서는 빠른 에러 확인을 위해 1번만 시도
    )

    print("\n" + "=" * 60)
    if success:
        print("🎉 [E2E 최종 결과] 완벽 성공! AI 분석부터 포스팅까지 파이프라인 합격!")
    else:
        print("❌ [E2E 최종 결과] 발행 실패... 브라우저 환경이나 요소를 확인하세요.")
    print("=" * 60)

if __name__ == "__main__":
    # Windows ProactorEventLoop 연결 (playwright 충돌 방지)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    run_e2e_test()
