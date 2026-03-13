import io
import json
import traceback
import asyncio
import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from PIL import Image
from google import genai
from google.genai import types
from ..core.config import settings
from ..schemas.post import AnalyzeResult, ContentBlock, ImageInfo

# --- [1. Response Schemas] ---

class VisualFact(BaseModel):
    image_index: int = Field(description="사진의 순번 (1부터 시작)")
    category: str = Field(description="EXTERIOR, INTERIOR, MENU, FOOD_ITEM:메뉴명, RECEIPT, MAP 중 하나")
    description: str = Field(description="사진 속 객관적 사실 묘사 (있는 그대로만)")

class FactExtraction(BaseModel):
    place_name: str = Field(description="매장 이름")
    visual_facts: List[VisualFact] = Field(description="사진 분석 결과 (절대 지어내지 말 것)")
    place_address: str = Field(description="정확한 주소")
    place_hours: str = Field(description="정확한 영업시간")
    place_parking: str = Field(description="주차 정보")
    place_phone: str = Field(description="전화번호")
    place_vibe: List[str]
    visitor_insight: Optional[str]
    recent_event: Optional[str]

class BlogPostBlock(BaseModel):
    type: str = "quote"
    value: str

class BlogPost(BaseModel):
    title: str
    blocks: List[BlogPostBlock]
    tags: List[str]

# --- [2. Gemini Multi-Agent Service] ---

class GeminiService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.signature_greeting = "여러분의 맛집 메이트! 욱스의 욱이, 오늘도 기분 좋게 인사드려요!"
        self.MODEL_ID = "gemini-2.5-flash" 
        print(f"🚀 GeminiService V7 (No Hallucination Mode) Initialized")

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
            print(f"\n📸 [1/2] Extracting raw facts from {count} images and data...")
            image_parts = [self._prepare_image_part(img) for img in images]
            
            raw_text = json.dumps(initial_facts, ensure_ascii=False)
            
            extract_prompt = f"""
            너는 아주 엄격한 팩트 체크 수사관이야. 아래 데이터를 분석해서 오직 '실제 존재하는 정보'만 추출해.
            
            [절대 금기 사항]
            - 사진에 없는 메뉴(예: 미소장국, 반찬, 사이드 메뉴 등)를 추측해서 적지 마.
            - 확인되지 않은 정보는 차라리 비워둬. 
            
            [추출 항목]
            1. 매장 이름, 주소, 영업시간, 주차 정보, 전화번호
            2. 사진별 카테고리 분류 및 눈에 보이는 그대로의 묘사
            
            [참고 데이터]: {raw_text[:15000]}
            """
            
            config_extract = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FactExtraction,
                temperature=0.0
            )
            
            response = self.client.models.generate_content(
                model=self.MODEL_ID,
                contents=[extract_prompt, *image_parts],
                config=config_extract
            )
            extracted = response.parsed
            
            await asyncio.sleep(1)
            
            print(f"✍️ [2/2] Writing blog with strict grounding...")
            
            # 실제 추출된 음식 메뉴만 필터링 (할루시네이션 방지)
            food_items = []
            for f in extracted.visual_facts:
                if f.category.startswith("FOOD_ITEM:"):
                    m = f.category.split(":")[1]
                    if m not in food_items: food_items.append(m)
            
            food_guide = "\n".join([f"- [음식:{m}]: 이 메뉴의 상세 설명 (사진 속 비주얼 위주로)" for m in food_items])
            has_menu = any(f.category == "MENU" for f in extracted.visual_facts)
            
            # [전문적인 한 줄 정보 포맷]
            concise_info = f"{extracted.place_name} / {extracted.place_address} / {extracted.place_hours} / {extracted.place_phone} / {extracted.place_parking}"

            write_prompt = f"""
            너는 네이버 블로그 인플루언서야. 아래 [추출된 팩트]에만 100% 기반해서 포스팅을 작성해.
            
            [추출된 팩트]
            {extracted.model_dump_json()}

            [섹션별 작성 가이드]
            1. [인사말]: "{self.signature_greeting}"로 시작.
            2. [매장 위치 & 정보]: **반드시 아래 내용만 한 줄로 작성해. 다른 말은 절대 하지 마.**
               내용: {concise_info}
            3. [외관] / 4. [내부]: 사진에 찍힌 그대로만 묘사해.
            5. [메뉴판]: ({'메뉴판 사진 내용을 상세히 설명' if has_menu else '생략'})
            6. 음식 섹션: **추출된 메뉴 {food_items} 외에는 절대 언급 금지.** 
            {food_guide}
            7. [총평 & 마무리]: 팩트 기반 소감.

            [중요 제약]
            - **미소장국, 반찬 등 사진이나 데이터에 없는 내용은 절대 언급하지 마.**
            - 모든 블록은 `type: "quote"`, `value`는 `[섹션명] 내용` 형식을 유지해.
            """
            
            config_write = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BlogPost,
                temperature=0.7,
                max_output_tokens=8192
            )
            
            response_post = self.client.models.generate_content(
                model=self.MODEL_ID,
                contents=write_prompt,
                config=config_write
            )
            final_post = response_post.parsed

            # 이미지 정보 조립
            image_info_list = []
            fact_map = {f.image_index: f for f in extracted.visual_facts}
            for i in range(1, count + 1):
                if i in fact_map:
                    f = fact_map[i]
                    image_info_list.append(ImageInfo(path="", category=f.category, description=f.description))
                else:
                    image_info_list.append(ImageInfo(path="", category="INTERIOR", description="추가 사진"))

            return AnalyzeResult(
                title=final_post.title,
                content="",
                blocks=[ContentBlock(type=b.type, value=b.value) for b in final_post.blocks],
                tags=final_post.tags,
                facts=extracted.model_dump(),
                images=image_info_list
            )
            
        except Exception as e:
            traceback.print_exc()
            raise e

    async def refine_content(self, title: str, content: str, facts: dict, style: str, images: List[ImageInfo] = [], instruction: str = None, template_name: str = None) -> AnalyzeResult:
        prompt = f"블로그 글 재구성:\n제목: {title}\n본문: {content}\n팩트: {json.dumps(facts)}\n요청사항: {instruction}"
        config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=BlogPost, temperature=0.7, max_output_tokens=8192)
        response = self.client.models.generate_content(model=self.MODEL_ID, contents=prompt, config=config)
        res = response.parsed
        return AnalyzeResult(title=res.title, content="", blocks=[ContentBlock(type=b.type, value=b.value) for b in res.blocks], tags=res.tags, facts=facts, images=images)

    async def patch_sections(self, current_blocks: List[ContentBlock], new_facts: dict) -> List[ContentBlock]:
        info = f"{new_facts.get('place_name', '매장')} / {new_facts.get('place_address', '주소')} / {new_facts.get('place_hours', '시간')} / {new_facts.get('place_phone', '번호')} / {new_facts.get('place_parking', '주차')}"
        return [ContentBlock(type="quote", value=f"[매장 위치 & 정보] {info}") if "[매장 위치 & 정보]" in b.value else b for b in current_blocks]

    async def summarize_place_info(self, raw_text: str) -> dict:
        prompt = f"플레이스 정보 요약: {raw_text[:10000]}"
        config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=FactExtraction, temperature=0.0)
        response = self.client.models.generate_content(model=self.MODEL_ID, contents=prompt, config=config)
        ext = response.parsed
        return ext.model_dump()

gemini_service = GeminiService()
