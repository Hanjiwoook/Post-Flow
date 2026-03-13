import os
import sys
import time

# 현재 디렉토리를 모듈 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# V2 엔진을 임포트합니다.
from app.services.automation.naver_v2 import naver_automation_v2

def test_publish_v2():
    print("🚀 [V2 통합 테스트] 네이버 스마트 자동 발행 시작")
    
    # 1. 테스트용 데이터 준비
    title = "Post Flow V2 정공법 통합 테스트 (성공 기원)"
    
    blocks = [
        {"type": "quote", "value": "[인사말] 안녕하세요! 드디어 인터리빙 V2 엔진 테스트를 시작합니다."},
        {"type": "quote", "value": "[외관] 여기는 매장 입구입니다. 아주 깔끔하죠?"},
        {"type": "quote", "value": "[음식:치즈버거] 육즙이 팡팡 터지는 치즈버거 비주얼 좀 보세요! 정말 맛있습니다."},
        {"type": "quote", "value": "[음식:콜라] 톡 쏘는 탄산이 매력적인 시원한 콜라입니다. 버거랑 찰떡궁합이죠!"},
        {"type": "divider", "value": ""},
        {"type": "quote", "value": "[총평 & 마무리] 성공적으로 메뉴별 매칭이 되었기를 바랍니다!"}
    ]
    
    facts = {"location": "쉐이크쉑 강남점"}

    # 2. 이미지 파일 찾기 (기존 이미지 활용)
    import glob
    found_images = glob.glob("..\\KakaoTalk_*.jpg") + glob.glob("KakaoTalk_*.jpg")
    
    image_paths = []
    images_data = []
    
    if len(found_images) >= 2:
        # 사진 1: 치즈버거로 가상 분류
        path1 = os.path.abspath(found_images[0])
        image_paths.append(path1)
        images_data.append({"path": path1, "category": "FOOD_ITEM:치즈버거"})
        print(f"📸 테스트 사진 1: FOOD_ITEM:치즈버거 -> {path1}")

        # 사진 2: 콜라로 가상 분류
        path2 = os.path.abspath(found_images[1])
        image_paths.append(path2)
        images_data.append({"path": path2, "category": "FOOD_ITEM:콜라"})
        print(f"📸 테스트 사진 2: FOOD_ITEM:콜라 -> {path2}")
    else:
        print("⚠️ 테스트용 이미지가 부족합니다 (최소 2장 필요).")

    # 3. V2 자동화 실행
    print("\n🤖 V2 봇 가동 중... 정공법(직접 클릭/타이핑)으로 도전합니다.")
    success = naver_automation_v2.publish(
        title=title, 
        blocks=blocks, 
        image_paths=image_paths, 
        images_data=images_data, 
        facts=facts
    )

    if success:
        print("\n✅ [V2 결과] 성공! 임시저장함에서 유령 입력이 해결되었는지 확인하세요.")
    else:
        print("\n❌ [V2 결과] 실패: 오류 발생")

if __name__ == "__main__":
    test_publish_v2()
