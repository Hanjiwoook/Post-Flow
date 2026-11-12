"""
WritingStyleService - 블로그 글쓰기 스타일 분석 및 프로필 관리
크롤링한 글 → Gemini 분석 → Style Profile JSON → 프롬프트 생성
"""
import json
import traceback
from typing import List, Optional, Dict
from datetime import datetime

from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db.models import WritingStyleProfile
from ..db.session import SessionLocal


# --- 스타일 프로필 응답 스키마 ---

class ToneAnalysis(BaseModel):
    formality: str = Field(description="말투 유형 (예: ~요체 위주, 반말 섞어 사용)")
    warmth: str = Field(description="따뜻함/차가움 정도")
    humor_level: str = Field(description="유머 수준 (없음/가벼움/높음)")
    enthusiasm: str = Field(description="열정/감탄사 사용 빈도")

class VocabularyAnalysis(BaseModel):
    favorite_expressions: List[str] = Field(description="자주 반복되는 표현 10개")
    emoji_patterns: str = Field(description="이모지/이모티콘 사용 패턴")
    sentence_endings: List[str] = Field(description="자주 쓰는 문장 어미 패턴 10개")
    avoided_expressions: List[str] = Field(description="이 블로거가 절대 안 쓸 것 같은 AI스러운 딱딱한 표현 5개")

class StructureAnalysis(BaseModel):
    intro_style: str = Field(description="도입부 스타일 (예: 일상 에피소드로 시작)")
    paragraph_length: str = Field(description="평균 문단 길이")
    section_flow: str = Field(description="전체 글의 섹션 흐름")
    closing_style: str = Field(description="마무리 스타일")

class WritingHabits(BaseModel):
    photo_description_style: str = Field(description="사진 설명 방식")
    personal_touch: str = Field(description="개인적 에피소드 삽입 방식")
    information_density: str = Field(description="정보 vs 감성 비율")

class StyleProfileSchema(BaseModel):
    tone: ToneAnalysis
    vocabulary: VocabularyAnalysis
    structure: StructureAnalysis
    writing_habits: WritingHabits
    sample_sentences: List[str] = Field(description="이 블로거 스타일이 가장 잘 드러나는 대표 문장 5~10개 발췌")
    overall_summary: str = Field(description="이 블로거의 글쓰기 스타일을 한 문단으로 요약")


class WritingStyleService:
    """블로그 글쓰기 스타일 분석 및 프로필 관리 서비스"""

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.MODEL_ID = "gemini-2.5-flash"
        print("[StyleService] WritingStyleService Initialized")

    async def analyze_style(self, texts: List[str]) -> dict:
        """
        여러 편의 블로그 글에서 공통 스타일 패턴을 추출한다.
        Gemini에게 분석 요청 → StyleProfile JSON 반환
        """
        n = len(texts)
        print(f"\n🔍 [StyleAnalyzer] {n}편의 글에서 스타일 분석 시작...")

        # 각 글 텍스트를 번호 매겨서 하나의 프롬프트로 구성
        texts_formatted = ""
        for i, text in enumerate(texts):
            # 텍스트가 너무 길면 앞부분만 사용 (토큰 절약)
            truncated = text[:3000] if len(text) > 3000 else text
            texts_formatted += f"\n\n--- [블로그 글 {i+1}] ---\n{truncated}"

        prompt = f"""너는 글쓰기 스타일 분석 전문가야.
아래는 한 블로거가 직접 작성한 블로그 글 {n}편이야.
이 블로거의 글쓰기 스타일을 아주 정밀하게 분석해줘.

[분석 포인트]
1. 톤 & 말투: 존댓말/반말 비율, 감탄사 패턴, 전체적인 분위기
2. 어휘 습관: 자주 반복되는 표현, 이모지 사용 패턴, 문장 어미 패턴
3. 구조적 특징: 문단 길이, 섹션 흐름, 도입부/마무리 패턴  
4. 글쓰기 습관: 사진 설명 방식, 개인 에피소드 삽입 방식, 정보 vs 감성 비율
5. 대표 문장: 이 블로거 스타일이 가장 잘 드러나는 실제 문장 5~10개를 원문 그대로 발췌
6. AI와 구별되는 핵심: 이 사람만의 독특한 표현이나 습관 (AI는 절대 이렇게 못 쓰는 것들)

[중요] "자주 쓰는 표현"과 "문장 어미"는 실제 텍스트에서 발견되는 것만 뽑을 것. 지어내지 마.
[중요] "AI스러운 표현"에는 "제공", "추천드립니다", "다양한", "특히" 같은 단어를 포함시켜.

{texts_formatted}
"""

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=StyleProfileSchema,
            temperature=0.2  # 분석은 낮은 temperature로 정확하게
        )

        try:
            response = self.client.models.generate_content(
                model=self.MODEL_ID,
                contents=prompt,
                config=config
            )
            result = response.parsed
            print(f"✅ [StyleAnalyzer] 스타일 분석 완료!")
            print(f"  📝 요약: {result.overall_summary[:100]}...")
            return result.model_dump()
        except Exception as e:
            traceback.print_exc()
            raise e

    async def select_few_shots(self, texts: List[str], count: int = 2) -> List[str]:
        """
        가장 대표적인 글 N편을 Few-shot 예시로 선별한다.
        전체 글 중에서 스타일이 가장 잘 드러나는 것을 Gemini에게 고르게 함.
        """
        if len(texts) <= count:
            # 글이 선별 수보다 적으면 전체 사용 (앞부분만)
            return [t[:2000] for t in texts]

        n = len(texts)
        texts_summary = ""
        for i, text in enumerate(texts):
            preview = text[:500]
            texts_summary += f"\n[글 {i}] {preview}...\n"

        prompt = f"""아래 {n}편의 블로그 글 중에서, 이 블로거의 글쓰기 스타일이 가장 잘 드러나는 글 {count}편의 번호를 골라줘.
선택 기준: 개성 있는 표현, 자연스러운 말투, 감성적인 묘사가 풍부한 글

{texts_summary}

반드시 JSON 배열로 글 번호만 반환해. 예: [0, 3]
"""

        try:
            response = self.client.models.generate_content(
                model=self.MODEL_ID,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.1)
            )
            
            # 응답에서 숫자 배열 추출
            text = response.text.strip()
            # JSON 배열 형태에서 숫자 추출
            indices = json.loads(text) if text.startswith('[') else [0, 1]
            
            # 유효 인덱스만 필터링
            valid_indices = [i for i in indices if 0 <= i < len(texts)][:count]
            if not valid_indices:
                valid_indices = list(range(min(count, len(texts))))
            
            # 선택된 글 텍스트 반환 (2000자 제한)
            selected = [texts[i][:2000] for i in valid_indices]
            print(f"📚 [StyleAnalyzer] Few-shot 예시 선별 완료: 글 번호 {valid_indices}")
            return selected
            
        except Exception as e:
            print(f"⚠️ Few-shot 선별 실패, 첫 {count}개 사용: {e}")
            return [t[:2000] for t in texts[:count]]

    def generate_style_prompt(self, profile_data: dict, few_shot_examples: List[str]) -> str:
        """
        Style Profile + Few-shot Examples를 AI 프롬프트용 텍스트로 변환한다.
        이 텍스트를 GeminiService의 writer_prompt에 주입하면 된다.
        """
        if not profile_data:
            return ""

        tone = profile_data.get('tone', {})
        vocab = profile_data.get('vocabulary', {})
        structure = profile_data.get('structure', {})
        habits = profile_data.get('writing_habits', {})
        sample_sentences = profile_data.get('sample_sentences', [])

        # 스타일 가이드 텍스트 생성
        style_guide = f"""[🎨 글쓰기 스타일 가이드 - 반드시 이 스타일을 정확히 모방해서 작성할 것]

[톤 & 말투]
- 말투 유형: {tone.get('formality', '알 수 없음')}
- 분위기: {tone.get('warmth', '알 수 없음')}
- 유머: {tone.get('humor_level', '알 수 없음')}
- 감탄사: {tone.get('enthusiasm', '알 수 없음')}

[어휘 패턴 - 이 표현들을 적극 활용할 것]
- 자주 쓰는 표현: {', '.join(vocab.get('favorite_expressions', []))}
- 문장 어미 패턴: {', '.join(vocab.get('sentence_endings', []))}
- 이모지 패턴: {vocab.get('emoji_patterns', '알 수 없음')}

[절대 사용 금지 표현 - 이 표현이 들어가면 AI가 쓴 티가 남]
{', '.join(vocab.get('avoided_expressions', ['제공', '추천드립니다', '다양한']))}

[글 구조]
- 도입부: {structure.get('intro_style', '알 수 없음')}
- 문단 길이: {structure.get('paragraph_length', '알 수 없음')}
- 흐름: {structure.get('section_flow', '알 수 없음')}
- 마무리: {structure.get('closing_style', '알 수 없음')}

[개성]
- 사진 설명: {habits.get('photo_description_style', '알 수 없음')}
- 에피소드: {habits.get('personal_touch', '알 수 없음')}
- 정보밀도: {habits.get('information_density', '알 수 없음')}

[이 블로거의 실제 대표 문장 - 이 톤을 그대로 따라할 것]
"""
        for s in sample_sentences[:5]:
            style_guide += f'- "{s}"\n'

        # Few-shot 예시 추가
        if few_shot_examples:
            style_guide += "\n[참고: 이 블로거가 실제로 작성한 글 예시]\n"
            for i, example in enumerate(few_shot_examples):
                style_guide += f"\n--- 예시 {i+1} ---\n{example}\n"
            style_guide += "\n[위 예시들의 말투, 어미, 감탄사, 이모지 사용 패턴을 정확히 따라해서 작성할 것]\n"

        return style_guide

    def get_active_profile(self) -> Optional[dict]:
        """현재 활성화된 스타일 프로필을 DB에서 조회한다."""
        db = SessionLocal()
        try:
            profile = db.query(WritingStyleProfile).filter(
                WritingStyleProfile.is_active == True
            ).first()
            
            if profile:
                return {
                    'id': profile.id,
                    'name': profile.name,
                    'blog_id': profile.blog_id,
                    'profile_data': profile.profile_data,
                    'few_shot_examples': profile.few_shot_examples or [],
                    'crawled_posts_count': profile.crawled_posts_count,
                    'is_active': profile.is_active,
                }
            return None
        finally:
            db.close()

    async def learn_from_blog(self, blog_id: str, profile_name: str, max_posts: int = 5) -> dict:
        """
        전체 학습 파이프라인: 크롤링 → 스타일 분석 → DB 저장
        이 메서드 하나로 스타일 학습이 완료된다.
        """
        from .blog_crawler import blog_crawler

        print(f"\n🎓 [StyleLearning] 학습 시작: blog_id='{blog_id}', profile='{profile_name}'")

        # 1. 크롤링
        print("\n📡 [Step 1/3] 블로그 글 크롤링...")
        crawled_posts = await blog_crawler.crawl_all(blog_id, max_posts)
        
        if not crawled_posts:
            raise ValueError(f"블로그 '{blog_id}'에서 글을 수집할 수 없습니다. 블로그 ID를 확인해주세요.")

        texts = [post['content'] for post in crawled_posts if post.get('content')]
        
        if not texts:
            raise ValueError("수집된 글에서 본문을 추출할 수 없습니다.")

        print(f"  ✅ {len(texts)}편 수집 완료")

        # 2. 스타일 분석
        print("\n🔍 [Step 2/3] 스타일 분석 중...")
        profile_data = await self.analyze_style(texts)

        # 3. Few-shot 예시 선별
        print("\n📚 [Step 3/3] Few-shot 예시 선별 중...")
        few_shots = await self.select_few_shots(texts, count=2)

        # 4. DB 저장
        print("\n💾 DB에 프로필 저장 중...")
        db = SessionLocal()
        try:
            # 기존 활성 프로필 비활성화
            db.query(WritingStyleProfile).filter(
                WritingStyleProfile.is_active == True
            ).update({'is_active': False})

            # 같은 이름의 기존 프로필이 있으면 업데이트
            existing = db.query(WritingStyleProfile).filter(
                WritingStyleProfile.name == profile_name
            ).first()

            if existing:
                existing.blog_id = blog_id
                existing.profile_data = profile_data
                existing.sample_texts = texts
                existing.few_shot_examples = few_shots
                existing.crawled_posts_count = len(texts)
                existing.is_active = True
                existing.updated_at = datetime.utcnow()
                profile_id = existing.id
            else:
                new_profile = WritingStyleProfile(
                    name=profile_name,
                    blog_id=blog_id,
                    profile_data=profile_data,
                    sample_texts=texts,
                    few_shot_examples=few_shots,
                    crawled_posts_count=len(texts),
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(new_profile)
                db.flush()
                profile_id = new_profile.id

            db.commit()
            print(f"✅ [StyleLearning] 학습 완료! 프로필 ID: {profile_id}")

            return {
                'profile_id': profile_id,
                'profile_name': profile_name,
                'blog_id': blog_id,
                'crawled_posts_count': len(texts),
                'profile_data': profile_data,
                'few_shot_count': len(few_shots),
                'status': 'SUCCESS'
            }
        except Exception as e:
            db.rollback()
            traceback.print_exc()
            raise e
        finally:
            db.close()


# 싱글톤 인스턴스
writing_style_service = WritingStyleService()
