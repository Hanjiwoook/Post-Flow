"""
Style API - 글쓰기 스타일 학습/관리 엔드포인트
POST /style/learn: 블로그 크롤링 → 스타일 분석 → 프로필 저장
GET  /style/profiles: 저장된 프로필 목록
PUT  /style/profiles/{id}/activate: 활성 프로필 변경
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from ....services.writing_style_service import writing_style_service
from ....schemas.common import CommonResponse
from ....db.session import get_db
from ....db.models import WritingStyleProfile
from ....core.config import settings

router = APIRouter()


# --- Request/Response 스키마 ---

class StyleLearnRequest(BaseModel):
    blog_id: Optional[str] = None  # 미입력 시 .env의 GF_BLOG_ID 사용
    profile_name: str = "기본 스타일"
    max_posts: int = 5

class StyleProfileResponse(BaseModel):
    id: int
    name: str
    blog_id: Optional[str] = None
    crawled_posts_count: int = 0
    is_active: bool = False
    profile_summary: Optional[str] = None  # overall_summary
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class StylePreviewRequest(BaseModel):
    sample_text: str = "오늘 남자친구랑 홍대에 새로 생긴 라멘집에 갔다."


# --- API 엔드포인트 ---

@router.post("/learn", response_model=CommonResponse)
async def learn_writing_style(request: StyleLearnRequest):
    """
    블로그 ID를 받아서 크롤링 → 스타일 분석 → DB 저장을 한번에 수행한다.
    가장 핵심 API. 이거 한 번 호출하면 스타일 학습 완료!
    """
    blog_id = request.blog_id or settings.GF_BLOG_ID
    
    if not blog_id:
        return CommonResponse(
            success=False,
            message="블로그 ID가 필요합니다. 요청 body에 blog_id를 넣거나 .env에 GF_BLOG_ID를 설정해주세요.",
            error="MISSING_BLOG_ID"
        )

    try:
        result = await writing_style_service.learn_from_blog(
            blog_id=blog_id,
            profile_name=request.profile_name,
            max_posts=request.max_posts
        )
        return CommonResponse(
            success=True,
            message=f"스타일 학습 완료! {result['crawled_posts_count']}편의 글에서 패턴을 추출했습니다.",
            data=result
        )
    except ValueError as e:
        return CommonResponse(
            success=False,
            message=str(e),
            error="CRAWLING_FAILED"
        )
    except Exception as e:
        return CommonResponse(
            success=False,
            message=f"스타일 학습 중 오류가 발생했습니다: {str(e)}",
            error="LEARN_ERROR"
        )


@router.get("/profiles", response_model=CommonResponse)
async def list_profiles(db: Session = Depends(get_db)):
    """저장된 스타일 프로필 목록을 조회한다."""
    profiles = db.query(WritingStyleProfile).order_by(
        WritingStyleProfile.updated_at.desc()
    ).all()

    result = []
    for p in profiles:
        summary = None
        if p.profile_data and isinstance(p.profile_data, dict):
            summary = p.profile_data.get('overall_summary', '')
        
        result.append({
            'id': p.id,
            'name': p.name,
            'blog_id': p.blog_id,
            'crawled_posts_count': p.crawled_posts_count,
            'is_active': p.is_active,
            'profile_summary': summary,
            'created_at': p.created_at.isoformat() if p.created_at else None,
            'updated_at': p.updated_at.isoformat() if p.updated_at else None,
        })

    return CommonResponse(
        success=True,
        message=f"{len(result)}개의 프로필이 있습니다.",
        data=result
    )


@router.get("/profiles/{profile_id}", response_model=CommonResponse)
async def get_profile_detail(profile_id: int, db: Session = Depends(get_db)):
    """특정 스타일 프로필의 상세 정보를 조회한다."""
    profile = db.query(WritingStyleProfile).filter(
        WritingStyleProfile.id == profile_id
    ).first()

    if not profile:
        return CommonResponse(
            success=False,
            message="프로필을 찾을 수 없습니다.",
            error="NOT_FOUND"
        )

    return CommonResponse(
        success=True,
        message="프로필 조회 성공",
        data={
            'id': profile.id,
            'name': profile.name,
            'blog_id': profile.blog_id,
            'profile_data': profile.profile_data,
            'few_shot_examples': profile.few_shot_examples,
            'crawled_posts_count': profile.crawled_posts_count,
            'is_active': profile.is_active,
            'created_at': profile.created_at.isoformat() if profile.created_at else None,
            'updated_at': profile.updated_at.isoformat() if profile.updated_at else None,
        }
    )


@router.put("/profiles/{profile_id}/activate", response_model=CommonResponse)
async def activate_profile(profile_id: int, db: Session = Depends(get_db)):
    """특정 프로필을 활성화하고 나머지는 비활성화한다."""
    profile = db.query(WritingStyleProfile).filter(
        WritingStyleProfile.id == profile_id
    ).first()

    if not profile:
        return CommonResponse(
            success=False,
            message="프로필을 찾을 수 없습니다.",
            error="NOT_FOUND"
        )

    # 모든 프로필 비활성화
    db.query(WritingStyleProfile).update({'is_active': False})
    
    # 선택한 프로필 활성화
    profile.is_active = True
    profile.updated_at = datetime.utcnow()
    db.commit()

    return CommonResponse(
        success=True,
        message=f"'{profile.name}' 프로필이 활성화되었습니다. 이제 이 스타일로 글이 생성됩니다!"
    )


@router.delete("/profiles/{profile_id}", response_model=CommonResponse)
async def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    """스타일 프로필을 삭제한다."""
    profile = db.query(WritingStyleProfile).filter(
        WritingStyleProfile.id == profile_id
    ).first()

    if not profile:
        return CommonResponse(
            success=False,
            message="프로필을 찾을 수 없습니다.",
            error="NOT_FOUND"
        )

    name = profile.name
    db.delete(profile)
    db.commit()

    return CommonResponse(
        success=True,
        message=f"'{name}' 프로필이 삭제되었습니다."
    )


@router.post("/preview", response_model=CommonResponse)
async def preview_style(request: StylePreviewRequest):
    """
    현재 활성 스타일로 샘플 문장을 변환해본다. (테스트/미리보기용)
    """
    from google import genai
    from google.genai import types

    active_profile = writing_style_service.get_active_profile()
    if not active_profile:
        return CommonResponse(
            success=False,
            message="활성화된 스타일 프로필이 없습니다. 먼저 /style/learn으로 학습해주세요.",
            error="NO_ACTIVE_PROFILE"
        )

    style_prompt = writing_style_service.generate_style_prompt(
        active_profile['profile_data'],
        active_profile['few_shot_examples']
    )

    prompt = f"""{style_prompt}

[미션] 아래 문장을 위 블로거의 스타일로 블로그 본문 한 문단(3~5문장)으로 확장해줘.
AI스러운 표현 절대 금지. 위 예시 톤을 정확히 따라할 것.

원본: {request.sample_text}
"""

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.7)
        )
        return CommonResponse(
            success=True,
            message="스타일 미리보기 생성 완료",
            data={
                'original': request.sample_text,
                'styled': response.text,
                'profile_name': active_profile['name']
            }
        )
    except Exception as e:
        return CommonResponse(
            success=False,
            message=f"미리보기 생성 실패: {str(e)}",
            error="PREVIEW_ERROR"
        )
