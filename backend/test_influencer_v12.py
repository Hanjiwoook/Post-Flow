import asyncio
import os
import json
from PIL import Image, ImageDraw
import io
from app.services.gemini_service import gemini_service
from app.schemas.post import AnalyzeResult

def create_sample_image(text, color):
    """테스트용 샘플 이미지 생성"""
    img = Image.new('RGB', (800, 600), color=color)
    d = ImageDraw.Draw(img)
    d.text((10, 10), text, fill=(255, 255, 255))
    return img

async def test_influencer_layout():
    print("🚀 [V12 Influencer Mode] 레이아웃 생성 테스트 시작...")
    
    # 1. 샘플 이미지 5장 준비
    sample_images = [
        create_sample_image("EXTERIOR: 욱스라멘 간판", (50, 50, 200)),  # 0: 외관
        create_sample_image("INTERIOR: 우드톤 다찌석", (100, 50, 50)),   # 1: 내부
        create_sample_image("MENU: 돈코츠라멘 10,000원", (50, 100, 50)), # 2: 메뉴판
        create_sample_image("FOOD: 진한 국물의 돈코츠라멘", (200, 150, 50)), # 3: 음식 1
        create_sample_image("FOOD: 바삭한 차슈 추가", (150, 100, 50)),     # 4: 음식 2
    ]
    
    # 2. 가상의 매장 정보 (사용자 힌트 포함)
    initial_facts = {
        "place_name": "욱스라멘 강남점",
        "address": "서울 강남구 테헤란로 123",
        "business_hours": "매일 11:00 - 21:00",
        "parking": "건물 지하 주차 가능 (1시간 무료)",
        "visitor_insight": "자가제면이라 면발이 아주 쫄깃하고 국물이 깊기로 유명한 곳이에요.",
        "image_hints": [
            "깔끔한 일본식 라멘집 외관이에요",
            "혼밥하기 좋은 다찌석 위주예요",
            "메뉴는 돈코츠와 소유 두 가지만 집중해요",
            "차슈가 정말 두툼한 돈코츠라멘이에요",
            "차슈를 추가했는데 불향이 가득해요"
        ]
    }

    try:
        # 3. AI 분석 및 집필 호출
        print("🤖 AI가 인플루언서 빙의해서 글을 쓰는 중... (약 10~20초 소요)")
        result = await gemini_service.analyze_images(
            images=sample_images,
            style="emotional",
            initial_facts=initial_facts
        )

        # 4. 결과 출력 및 분석
        print("\n" + "="*50)
        print(f"✨ [제목]: {result.title}")
        print("="*50)
        
        print("\n🧩 [생성된 레이아웃 블록 리스트]:")
        for i, block in enumerate(result.blocks):
            b_type = block.type
            b_val = block.value or ""
            b_idx = block.image_index
            b_style = block.style or ""
            
            icon = "📝" if b_type == "text" else "📸" if b_type == "image" else "🖋️" if b_type == "quote" else "➖" if b_type == "divider" else "📍"
            
            info = f"[{b_type}]"
            if b_idx is not None: info += f" (사진 {b_idx}번)"
            if b_style: info += f" (스타일: {b_style})"
            
            content = b_val[:50].replace('\n', ' ') + "..." if len(b_val) > 50 else b_val
            print(f"{i+1}. {icon} {info.ljust(25)} | {content}")

        print("\n" + "="*50)
        print("✅ 테스트 완료! AI가 아주 똑똑하게 레이아웃을 짰네.")
        print("이제 이 JSON 데이터를 네이버 블로그 자동화 엔진에 넣으면 잡지처럼 발행돼!")
        
        # 결과 파일로 저장 (디버깅용)
        with open("debug_influencer_test.json", "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
        print("\n💾 상세 결과는 'debug_influencer_test.json'에 저장되었어.")

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # PYTHONPATH 설정 없이 실행 가능하도록 경로 조정
    import sys
    sys.path.append(os.getcwd())
    asyncio.run(test_influencer_layout())
