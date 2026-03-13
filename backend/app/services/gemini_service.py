import io
import json
import traceback
import asyncio
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from PIL import Image
from google import genai
from google.genai import types
from ..core.config import settings
from ..schemas.post import AnalyzeResult, ContentBlock, ImageInfo

# --- [1. Response Schemas] ---

# 사진 분석 결과 (반드시 입력된 사진 개수와 순서가 일치해야 함)
class ImageAnalysis(BaseModel):
    category: str = Field(description="EXTERIOR, INTERIOR, MENU, FOOD_ITEM:메뉴명, RECEIPT, MAP 중 하나 (음식은 정확한 메뉴명 기입)")
    description: str = Field(description="사진에 보이는 그대로의 객관적 팩트 (절대 지어내지 말 것)")

class ImageAnalysisList(BaseModel):
    results: List[ImageAnalysis]

# 매장 정보 요약
class PlaceSummary(BaseModel):
    place_name: str
    address: str
    phone: str
    business_hours: str
    parking: str
    owner_intro: Optional[str] = None
    visitor_insight: Optional[str] = None

# 블로그 본문 블록
class BlogPostBlock(BaseModel):
    type: str = "quote"
    value: str = Field(description="반드시 '[섹션명] 내용' 형식")

# 최종 블로그 포스팅
class BlogPost(BaseModel):
    title: str = Field(description="클릭을 유도하는 센스있는 블로그 제목")
    blocks: List[BlogPostBlock]
    tags: List[str]

# --- [2. Gemini Multi-Agent Service V12] ---

class GeminiService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.signature_greeting = "여러분의 맛집 메이트! 욱스의 욱이, 오늘도 기분 좋게 인사드려요!"
        self.MODEL_ID = "gemini-2.5-flash"
        print(f"🚀 GeminiService V12 (Ironclad Editor Mode) Initialized")

    def _prepare_image_part(self, img: Image.Image) -> types.Part:
        if max(img.size) > 1024:
            ratio = 1024 / max(img.size)
            img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)), Image.LANCZOS)
        img_byte_arr = io.BytesIO()
        if img.mode != "RGB": img = img.convert("RGB")
        img.save(img_byte_arr, format='JPEG', quality=85)
        return types.Part.from_bytes(data=img_byte_arr.getvalue(), mime_type="image/jpeg")

    async def analyze_images(self, images: List[Image.Image], style: str, template_name: str = None, initial_facts: dict = {}) -> AnalyzeResult:
        try:
            count = len(images)
            print(f"\n📸 [1/3] Extracting strict image facts ({count} images)...")
            image_parts = [self._prepare_image_part(img) for img in images]
            
            # 사용자 힌트
            user_hints = initial_facts.get('image_hints', [])
            hints_str = "\n".join([f"사진 {i+1} 힌트: {h}" for i, h in enumerate(user_hints) if h])
            
            # 1. 시각 정보 엄격 추출 (순서 강제)
            vision_prompt = f"""
            내가 {count}장의 사진을 순서대로 줄 거야.
            너는 반드시 이 사진들의 순서에 맞춰서 정확히 {count}개의 결과를 반환해야 해. 순서를 섞거나 누락하면 절대 안 돼.
            
            [사용자 힌트 (최우선 반영)]:
            {hints_str}
            
            [미션]
            - 건물의 밖, 간판 -> EXTERIOR
            - 매장 내부, 테이블 -> INTERIOR
            - 메뉴판 -> MENU
            - 음식 -> FOOD_ITEM:메뉴명 (메뉴명은 힌트나 사진을 보고 정확히 적을 것)
            - 설명은 눈에 보이는 사실만 적고, "일본 현지 느낌", "한적한" 같은 주관적 감상은 배제해.
            """
            config_vision = types.GenerateContentConfig(response_mime_type="application/json", response_schema=ImageAnalysisList, temperature=0.0)
            res_vision = self.client.models.generate_content(model=self.MODEL_ID, contents=[vision_prompt, *image_parts], config=config_vision)
            vision_data = res_vision.parsed.results

            # 만약 개수가 안 맞으면 강제 보정 (이미지 꼬임 완벽 방지)
            if len(vision_data) < count:
                vision_data.extend([ImageAnalysis(category="INTERIOR", description="추가 사진")] * (count - len(vision_data)))
            elif len(vision_data) > count:
                vision_data = vision_data[:count]

            await asyncio.sleep(2)

            print(f"🔍 [2/3] Extracting place data...")
            # 2. 매장 정보 요약
            raw_text = json.dumps(initial_facts, ensure_ascii=False)
            data_prompt = f"아래 데이터에서 매장 핵심 정보만 뽑아줘. 과거 정보는 무시해.\n{raw_text[:15000]}"
            config_data = types.GenerateContentConfig(response_mime_type="application/json", response_schema=PlaceSummary, temperature=0.0)
            res_data = self.client.models.generate_content(model=self.MODEL_ID, contents=data_prompt, config=config_data)
            place_data = res_data.parsed

            concise_info = f"{place_data.place_name} / {place_data.address} / {place_data.business_hours} / {place_data.phone} / {place_data.parking}"

            await asyncio.sleep(2)

            print(f"✍️ [3/3] Writing full blog post without hallucination...")
            # 3. 블로그 원샷 집필
            food_items = sorted(list(set([v.category.split(":")[1] for v in vision_data if v.category.startswith("FOOD_ITEM:")])))
            has_menu = any(v.category == "MENU" for v in vision_data)
            
            # 작가에게 줄 팩트 정리
            fact_list_str = "\n".join([f"- 사진 {i+1} ({v.category}): {v.description}" for i, v in enumerate(vision_data)])
            food_guide = "\n".join([f"   - [음식:{m}]: 사진 팩트 기반 상세 묘사" for m in food_items])

            writer_prompt = f"""
            너는 10만 팔로워 맛집 블로거야. 아래 [제공된 팩트]만 사용해서 완벽한 포스팅을 하나로 완성해줘.
            
            [절대 금지 사항 - 할루시네이션 방지]
            1. "한적한 골목길", "일본 현지 느낌" 등 팩트에 없는 분위기를 지어내지 마.
            2. 제공된 음식({food_items}) 외에 미소장국, 반찬 등 없는 메뉴는 절대 언급하지 마.
            
            [제공된 팩트]
            {fact_list_str}
            - 매장 인사이트: {place_data.visitor_insight}

            [필수 작성 섹션 - 이름 변경 불가]
            1. [인사말]: 반드시 "{self.signature_greeting}"로 시작. 풍부하게 묘사.
            2. [매장 위치 & 정보]: 아래 텍스트만 딱 한 줄로 출력.
               {concise_info}
            3. [외관]: EXTERIOR 사진 내용만 묘사.
            4. [내부]: INTERIOR 사진 내용만 묘사.
            {f"5. [메뉴판]: MENU 사진 내용 묘사." if has_menu else ""}
            6. 음식 섹션 (메뉴별 개별 작성):
            {food_guide}
            7. [총평 & 마무리]: 소감 및 추천 여부.

            각 블록의 value는 반드시 `[섹션명] 내용` 형식이어야 해. 외관과 내부를 복사붙여넣기 하지 말고 각각의 특징을 명확히 써.
            """
            
            config_write = types.GenerateContentConfig(response_mime_type="application/json", response_schema=BlogPost, temperature=0.7, max_output_tokens=8192)
            res_write = self.client.models.generate_content(model=self.MODEL_ID, contents=writer_prompt, config=config_write)
            final_post = res_write.parsed

            # 이미지 정보 최종 매핑 (순서 100% 보장)
            image_info_list = []
            for i in range(count):
                v = vision_data[i]
                image_info_list.append(ImageInfo(path="", category=v.category, description=v.description))

            return AnalyzeResult(
                title=final_post.title,
                content="",
                blocks=[ContentBlock(type=b.type, value=b.value) for b in final_post.blocks],
                tags=final_post.tags,
                facts=place_data.model_dump(),
                images=image_info_list
            )
        except Exception as e:
            traceback.print_exc()
            raise e

    async def refine_content(self, title: str, content: str, facts: dict, style: str, images: List[ImageInfo] = [], instruction: str = None, template_name: str = None) -> AnalyzeResult:
        prompt = f"재구성:\n제목:{title}\n본문:{content}\n팩트:{json.dumps(facts)}\n요청:{instruction}"
        config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=BlogPost, temperature=0.7, max_output_tokens=8192)
        response = self.client.models.generate_content(model=self.MODEL_ID, contents=prompt, config=config)
        res = response.parsed
        return AnalyzeResult(title=res.title, content="", blocks=[ContentBlock(type=b.type, value=b.value) for b in res.blocks], tags=res.tags, facts=facts, images=images)

    async def patch_sections(self, current_blocks: List[ContentBlock], new_facts: dict) -> List[ContentBlock]:
        info = f"{new_facts.get('place_name', '매장')} / {new_facts.get('address', '주소')} / {new_facts.get('business_hours', '시간')} / {new_facts.get('phone', '번호')} / {new_facts.get('parking', '주차')}"
        return [ContentBlock(type="quote", value=f"[매장 위치 & 정보] {info}") if "[매장 위치 & 정보]" in b.value else b for b in current_blocks]

    async def summarize_place_info(self, raw_text: str) -> dict:
        prompt = f"정보 요약: {raw_text[:10000]}"
        config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=PlaceSummary, temperature=0.0)
        try:
            res = self.client.models.generate_content(model=self.MODEL_ID, contents=prompt, config=config)
            return res.parsed.model_dump()
        except: return {}

gemini_service = GeminiService()
