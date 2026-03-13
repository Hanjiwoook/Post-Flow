import os
import sys
import time

# 현재 디렉토리를 모듈 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.automation.naver import naver_automation

def test_publish_integrated():
    print("🚀 [통합 테스트] 네이버 스마트 자동 발행 시작")
    
    # 1. 테스트용 데이터 준비
    title = "Post Flow 스마트 자동화 통합 테스트 (이미지+지도+인용구)"
    
    # 7단계 구조 중 일부 테스트
    blocks = [
        {"type": "quote", "value": "[인사말] 안녕하세요! 오늘은 Post Flow의 새로운 기능을 테스트 중입니다."},
        {"type": "quote", "value": "[매장 위치 & 정보] 여기는 강남역 인근의 핫플레이스입니다."},
        {"type": "quote", "value": "[외관] 매장 입구가 아주 세련되고 눈에 잘 띄네요."},
        {"type": "quote", "value": "[음식] 드디어 기다리던 메인 메뉴가 나왔습니다. 비주얼이 대박이에요!"},
        {"type": "divider", "value": ""},
        {"type": "quote", "value": "[총평 & 마무리] 전체적으로 만족스러운 경험이었습니다. 추천해요!"}
    ]
    
    facts = {
        "location": "쉐이크쉑 강남점",
        "ordered_menu": "쉑버거, 치즈 프라이",
        "parking": "인근 유료 주차장 이용"
    }

    # 2. 이미지 파일 찾기 (루트 폴더의 KakaoTalk_ 이미지 등 활용)
    import glob
    found_images = glob.glob("..\\KakaoTalk_*.jpg") + glob.glob("KakaoTalk_*.jpg")
    
    image_paths = []
    images_data = []
    
    if found_images:
        # 첫 번째 사진은 '외관'으로, 두 번째 사진은 '음식'으로 가상 분류
        for i, img in enumerate(found_images[:2]):
            abs_path = os.path.abspath(img)
            image_paths.append(abs_path)
            category = "EXTERIOR" if i == 0 else "FOOD_MAIN"
            images_data.append({"path": abs_path, "category": category})
            print(f"📸 테스트 이미지 {i+1}: {category} -> {abs_path}")
    else:
        print("⚠️ 테스트용 이미지가 없습니다. 텍스트와 지도만 테스트합니다.")

    # 3. 자동화 실행 (브라우저가 뜨는 것을 지켜보세요!)
    print("\n🤖 봇 가동 중... 네이버 로그인 및 에디터 진입을 시도합니다.")
    success = naver_automation.publish(
        title=title, 
        blocks=blocks, 
        image_paths=image_paths, 
        images_data=images_data, 
        facts=facts
    )

    if success:
        print("\n✅ [테스트 결과] 성공! 네이버 임시저장함에서 결과를 확인하세요.")
    else:
        print("\n❌ [테스트 결과] 실패: 로직 수행 중 오류가 발생했습니다.")

if __name__ == "__main__":
    test_publish_integrated()
