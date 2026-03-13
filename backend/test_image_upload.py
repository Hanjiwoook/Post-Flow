import os
import sys
import time

# 현재 디렉토리를 모듈 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# V2 엔진을 임포트합니다.
from app.services.automation.naver_v2 import naver_automation_v2

def test_image_bundle_logic():
    print("\n📸 [사진 묶음 업로드 테스트 시작]")
    
    # 테스트용 데이터 구성
    title = "Post Flow 사진 묶음 업로드 테스트"
    
    # 실제 존재하는 이미지 파일 경로 (기존 테스트 파일 활용)
    base_path = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_path)
    
    # 여러 장의 사진 테스트 (같은 파일을 여러 번 넣어 테스트)
    img1 = os.path.join(project_root, "KakaoTalk_20260130_150155348.jpg")
    img2 = os.path.join(project_root, "KakaoTalk_20260130_150155348_01.jpg")
    img3 = os.path.join(project_root, "KakaoTalk_20260130_150155348_02.jpg")
    
    # 이미지 데이터 구성
    images_data = [
        {"path": img1, "category": "EXTERIOR"},
        {"path": img2, "category": "EXTERIOR"},
        {"path": img3, "category": "EXTERIOR"},
    ]
    
    # 블록 데이터 (외관 섹션에서 3장이 한꺼번에 올라가는지 확인)
    blocks = [
        {"type": "quote", "value": "[외관] 테스트용 외관 설명입니다. 사진 3장이 콜라주로 올라가야 합니다."},
        {"type": "text", "value": "사진 업로드 후 45초(3장 x 15초)를 잘 기다리는지 확인하세요."},
    ]

    success = naver_automation_v2.publish(
        title=title,
        blocks=blocks,
        images_data=images_data
    )

    if success:
        print("\n✅ [테스트 결과] 성공! 네이버 에디터에서 사진이 콜라주로 잘 묶였는지 확인하세요.")
    else:
        print("\n❌ [테스트 결과] 실패")

if __name__ == "__main__":
    test_image_bundle_logic()
