import os
import sys
import asyncio
from PIL import Image
import io

# 프로젝트 루트를 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.gemini_service import gemini_service

async def test_image_classification_and_writing():
    print("--- 🚀 3단계: 이미지 자동 분류 및 정보성 글쓰기 테스트 ---")
    
    import glob
    # 루트 디렉토리에서 이미지 검색 (KakaoTalk_ 패턴)
    images_found = glob.glob("*.jpg")
    if not images_found:
        images_found = glob.glob("../" + "*.jpg")
    
    if not images_found:
        print("Error: No image files found.")
        return
        
    # 최대 5장까지 테스트
    images_to_use = images_found[:5]
    pil_images = [Image.open(img) for img in images_to_use]
    print(f"📷 {len(pil_images)}장의 이미지로 테스트 시작: {images_to_use}")
    
    # 1. AI 분석 및 분류 호출
    result = await gemini_service.analyze_images(pil_images, "informative")
    
    print("\n[📊 이미지 분류 결과]")
    for i, img_info in enumerate(result.images):
        print(f"사진 {i+1} ({images_to_use[i]}): {img_info.category}")
    
    print(f"\n[📝 생성된 정보성 제목]: {result.title}")
    
    print("\n[📄 생성된 본문 요약 (정보성 섹션 확인)]")
    # 요약 정보 박스가 있는지 확인하기 위해 상단 500자 출력
    print("-" * 50)
    print(result.content[:1000])
    print("-" * 50)

    # 마커 체크
    print("\n[📍 이미지 마커 배치 체크]")
    for i in range(1, len(pil_images) + 1):
        marker = f"[IMAGE{i}]"
        if marker in result.content:
            print(f"마커 {marker}: 배치 성공")
        else:
            print(f"마커 {marker}: 배치 실패")

async def main():
    try:
        await test_image_classification_and_writing()
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())
