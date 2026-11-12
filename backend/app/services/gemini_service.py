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

# 매장 정보 요약 (감성 데이터 포함 확장)
class PlaceSummary(BaseModel):
    place_name: str
    address: str
    phone: str
    business_hours: str
    parking: str
    # 감성/맥락 데이터
    visit_purpose: Optional[str] = Field(None, description="방문 목적 (예: 데이트, 혼밥, 회식 등)")
    special_note: Optional[str] = Field(None, description="사용자의 특별한 한 줄 메모/첫인상")
    rating: Optional[str] = Field(None, description="사용자의 별점이나 만족도 (1~5점)")
    owner_intro: Optional[str] = None
    visitor_insight: Optional[str] = None

# 블로그 본문 블록 (실제 ContentBlock 스키마와 동기화)
class BlogPostBlock(BaseModel):
    type: str = Field(description="text, quote, divider, image, map 중 하나")
    value: Optional[str] = Field(None, description="본문 텍스트 또는 인용구 내용")
    style: Optional[str] = Field(None, description="quote인 경우 'box' 또는 'line', divider인 경우 'line' 등")
    image_indices: List[int] = Field(default_factory=list, description="type이 image인 경우, 원본 사진 리스트에서의 0-based 인덱스 리스트 (콜라주용)")

# 최종 블로그 포스팅
class BlogPost(BaseModel):
    title: str = Field(description="클릭을 유도하는 센스있고 감성적인 블로그 제목 (이모지 포함 가능)")
    blocks: List[BlogPostBlock]
    tags: List[str]

# --- [2. Gemini Multi-Agent Service V12] ---

class GeminiService:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # 설정된 블로그 닉네임을 사용하도록 개선
        nickname = settings.BLOG_NICKNAME or "욱스"
        self.signature_greeting = f"안녕하세요! 맛집과 일상을 기록하는 '{nickname}'입니다. ✨ 오늘도 직접 발로 뛰어 찾은 리얼 맛집 정보를 전해드릴게요!"
        self.MODEL_ID = "gemini-2.5-flash"
        # 스타일 학습 서비스 연결
        from .writing_style_service import writing_style_service
        self.style_service = writing_style_service
        print(f"🚀 GeminiService V12 (Influencer + Style Learning) Initialized")

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
            hints_str = "\n".join([f"사진 {i} 힌트: {h}" for i, h in enumerate(user_hints) if h])
            
            # 1. 시각 정보 엄격 추출 (순서 강제)
            vision_prompt = f"""
            내가 {count}장의 사진을 순서대로 줄 거야. (0번부터 {count-1}번까지 인덱스 부여)
            너는 반드시 이 사진들의 순서에 맞춰서 정확히 {count}개의 분석 결과를 반환해야 해.
            
            [사용자 힌트 (최우선 반영)]:
            {hints_str}
            
            [카테고리 분류 가이드]
            - EXTERIOR: 매장 외부, 간판
            - INTERIOR: 내부 인테리어, 분위기
            - MENU: 메뉴판
            - FOOD_ITEM:메뉴명: 개별 음식 사진
            - MAP/RECEIPT: 지도나 영수증
            """
            config_vision = types.GenerateContentConfig(response_mime_type="application/json", response_schema=ImageAnalysisList, temperature=0.0)
            res_vision = self.client.models.generate_content(model=self.MODEL_ID, contents=[vision_prompt, *image_parts], config=config_vision)
            vision_data = res_vision.parsed.results

            if len(vision_data) < count:
                vision_data.extend([ImageAnalysis(category="INTERIOR", description="추가 정보 없음")] * (count - len(vision_data)))
            elif len(vision_data) > count:
                vision_data = vision_data[:count]

            await asyncio.sleep(2)

            print(f"🔍 [2/3] Extracting place data...")
            # 2. 매장 정보 요약
            raw_text = json.dumps(initial_facts, ensure_ascii=False)
            data_prompt = f"아래 데이터에서 매장 정보와 감성 정보를 뽑아줘.\n{raw_text[:15000]}"
            config_data = types.GenerateContentConfig(response_mime_type="application/json", response_schema=PlaceSummary, temperature=0.0)
            res_data = self.client.models.generate_content(model=self.MODEL_ID, contents=data_prompt, config=config_data)
            place_data = res_data.parsed

            await asyncio.sleep(2)

            print(f"✍️ [3/3] Writing influencer blog post with smart layout...")
            # 팩트 정리
            fact_list_str = "\n".join([f"- 사진 {i} ({v.category}): {v.description}" for i, v in enumerate(vision_data)])
            
            purpose = f"#{place_data.visit_purpose}" if place_data.visit_purpose else ""
            note = f"'{place_data.special_note}'" if place_data.special_note else ""
            rating_star = "⭐" * int(place_data.rating) if place_data.rating and place_data.rating.isdigit() else ""

            # 지역명 추출 (주소에서 '구' 또는 '동' 단위 추출)
            location_keyword = place_data.address.split(' ')[1] if len(place_data.address.split(' ')) > 1 else ""

            # ✨ 스타일 프로필 로드 (학습된 글쓰기 스타일이 있으면 적용)
            style_prompt_section = ""
            active_profile = self.style_service.get_active_profile()
            if active_profile:
                style_prompt_section = self.style_service.generate_style_prompt(
                    active_profile['profile_data'],
                    active_profile['few_shot_examples']
                )
                print(f"  🎨 스타일 프로필 적용: '{active_profile['name']}'")
            else:
                print(f"  ℹ️ 활성 스타일 프로필 없음 → 기본 인플루언서 스타일 사용")

            # 스타일 프로필 유무에 따라 프롬프트 분기
            if style_prompt_section:
                # 🎨 학습된 스타일이 있을 때: 해당 블로거 톤으로 작성
                writer_prompt = f"""
            {style_prompt_section}

            [위 블로거의 글쓰기 스타일을 완벽히 모방해서 아래 팩트 기반으로 블로그 글을 작성해줘]
            [AI스러운 표현 절대 금지. 위 예시의 말투, 어미, 감탄사, 이모지 패턴을 그대로 따라할 것]

            [핵심 목표: 네이버 검색 노출(SEO) 최적화 제목 생성]
            - 제목은 반드시 아래 공식을 따를 것: 
              `[지역명(동/구 단위)] [주요메뉴] 맛집 [매장명] : [감성적인 한줄평]`
            - 지역명 키워드: {location_keyword}
            - 매장명: {place_data.place_name}
            
            [작성 가이드 - 순서 및 태그 엄수]
            1. **[인사말] 섹션**: 반드시 `[인사말] {self.signature_greeting}`로 시작할 것.
            2. **사진 우선 배치**: 각 섹션에서 **사진(`image`) 블록을 먼저** 두고, 그 아래에 설명(`text`) 블록을 작성해.
            3. **콜라주 활용**: 외관(EXTERIOR)이나 내부(INTERIOR) 사진이 여러 장이면 하나의 `image` 블록에 `image_indices` 리스트로 묶어서 내보내.
            
            [블로그 템플릿 구조]
            1. [인사말]: {purpose}와 {note} 반영하여 작성.
            2. [매장 위치 & 정보]: `quote`(box)로 요약 정보.
            3. [외관]: 사진들(콜라주) 먼저 -> 설명 텍스트.
            4. [내부]: 사진들(콜라주) 먼저 -> 설명 텍스트.
            5. [메뉴판]: 사진 먼저 -> 설명 텍스트.
            6. [음식:메뉴명]: 사진 먼저 -> 상세 맛 묘사 텍스트.
            7. [총평 & 마무리]: {rating_star} 반영하여 마무리.

            [작성 규칙]
            - 모든 텍스트 블록의 시작은 반드시 `[섹션명]`으로 시작. (예: [인사말], [외관], [음식:라멘])
            - 각 섹션당 풍부한 묘사 필수.
            
            [제공된 팩트]
            - 매장명: {place_data.place_name}
            - 주소: {place_data.address}
            - 사진 정보: {fact_list_str}
            """
            else:
                # 기본 인플루언서 스타일 (스타일 프로필 없을 때)
                writer_prompt = f"""
            너는 대한민국 최고의 맛집 인플루언서이자 전문 에디터야. 아래 가이드에 맞춰 포스팅을 작성해줘.
            
            [핵심 목표: 네이버 검색 노출(SEO) 최적화 제목 생성]
            - 제목은 반드시 아래 공식을 따를 것: 
              `[지역명(동/구 단위)] [주요메뉴] 맛집 [매장명] : [감성적인 한줄평]`
            - 예시: `한남동 라멘 맛집 유카이도 : 인생 라멘을 만난 우드톤 감성 공간✨`
            - 지역명 키워드: {location_keyword}
            - 매장명: {place_data.place_name}
            
            [작성 가이드 - 순서 및 태그 엄수]
            1. **[인사말] 섹션**: 반드시 `[인사말] {self.signature_greeting}`로 시작할 것.
            2. **사진 우선 배치**: 각 섹션에서 **사진(`image`) 블록을 먼저** 두고, 그 아래에 설명(`text`) 블록을 작성해.
            3. **콜라주 활용**: 외관(EXTERIOR)이나 내부(INTERIOR) 사진이 여러 장이면 하나의 `image` 블록에 `image_indices` 리스트로 묶어서 내보내.
            
            [블로그 템플릿 구조]
            1. [인사말]: {purpose}와 {note} 반영하여 작성.
            2. [매장 위치 & 정보]: `quote`(box)로 요약 정보.
            3. [외관]: 사진들(콜라주) 먼저 -> 설명 텍스트.
            4. [내부]: 사진들(콜라주) 먼저 -> 설명 텍스트.
            5. [메뉴판]: 사진 먼저 -> 설명 텍스트.
            6. [음식:메뉴명]: 사진 먼저 -> 상세 맛 묘사 텍스트.
            7. [총평 & 마무리]: {rating_star} 반영하여 마무리.

            [작성 규칙]
            - 모든 텍스트 블록의 시작은 반드시 `[섹션명]`으로 시작. (예: [인사말], [외관], [음식:라멘])
            - 각 섹션당 풍부한 묘사 필수.
            
            [제공된 팩트]
            - 매장명: {place_data.place_name}
            - 주소: {place_data.address}
            - 사진 정보: {fact_list_str}
            """
            
            config_write = types.GenerateContentConfig(response_mime_type="application/json", response_schema=BlogPost, temperature=0.8, max_output_tokens=8192)
            res_write = self.client.models.generate_content(model=self.MODEL_ID, contents=writer_prompt, config=config_write)
            final_post = res_write.parsed

            return AnalyzeResult(
                title=final_post.title,
                content="",
                blocks=[ContentBlock(type=b.type, value=b.value, style=b.style, image_indices=b.image_indices) for b in final_post.blocks],
                tags=final_post.tags,
                facts=place_data.model_dump(),
                images=[ImageInfo(path="", category=v.category, description=v.description) for v in vision_data]
            )
        except Exception as e:
            traceback.print_exc()
            raise e

    async def refine_content(self, title: str, content: str, blocks: list = [], facts: dict = {}, style: str = "professional", images: List[ImageInfo] = [], instruction: str = None, template_name: str = None) -> AnalyzeResult:
        # 현재 블록 데이터를 텍스트로 변환하여 AI에게 전달
        blocks_text = ""
        for i, b in enumerate(blocks):
            b_dict = b.model_dump() if hasattr(b, "model_dump") else b
            b_type = b_dict.get("type", "text")
            b_value = b_dict.get("value", "") or ""
            b_indices = b_dict.get("image_indices", [])
            if b_value:
                blocks_text += f"[블록 {i}] type={b_type}, image_indices={b_indices}\n{b_value}\n\n"

        prompt = f"""아래는 현재 블로그 포스팅의 전체 본문이야. 사용자가 특정 부분만 수정해달라고 요청했어.

[현재 제목]: {title}

[현재 본문 블록들]:
{blocks_text}

[사용자 수정 요청]: {instruction}

[절대 규칙]
1. 사용자가 요청한 부분만 정확히 수정하고, 나머지 블록은 절대 삭제하거나 변경하지 마.
2. 블록의 type, 순서, image_indices를 반드시 그대로 유지해.
3. 전체 블록 개수도 동일하게 유지해. 새 블록을 추가하거나 기존 블록을 합치지 마.
4. 수정이 필요 없는 블록의 value는 원문 그대로 복사해서 내보내.
"""
        config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=BlogPost, temperature=0.4, max_output_tokens=8192)
        response = self.client.models.generate_content(model=self.MODEL_ID, contents=prompt, config=config)
        res = response.parsed
        
        # 응답 블록에 원본 image_indices 복원
        result_blocks = []
        original_blocks = [b.model_dump() if hasattr(b, "model_dump") else b for b in blocks]
        for i, b in enumerate(res.blocks):
            indices = b.image_indices if b.image_indices else []
            # 원본 블록에서 image_indices 복원 (AI가 누락했을 경우)
            if not indices and i < len(original_blocks):
                indices = original_blocks[i].get("image_indices", [])
            result_blocks.append(ContentBlock(type=b.type, value=b.value, style=b.style, image_indices=indices))
        
        return AnalyzeResult(title=res.title, content="", blocks=result_blocks, tags=res.tags, facts=facts, images=images)

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
