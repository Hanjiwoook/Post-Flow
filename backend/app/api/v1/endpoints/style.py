"""
Style API - 저장된 글쓰기 스타일 프로필 관리
GET    /style/profiles: 저장된 프로필 목록
GET    /style/profiles/{id}: 프로필 상세 (예시 글 포함)
PUT    /style/profiles/{id}/activate: 활성 프로필 변경 (글쓰기가 활성 프로필의 예시 글을 말투 참고로 쓴다)
DELETE /style/profiles/{id}: 프로필 삭제

11/19 (4-5 Gemini 정리): Gemini로 새 프로필을 만들던 /style/learn과 /style/preview는 지웠다
(크레딧 소진으로 동작하지 않았고, 지금 프로필로 충분하다). 자세한 사정은 services/writing_style_service.py.
"""
from fastapi import APIRouter, Depends
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from ....schemas.common import CommonResponse
from ....db.session import get_db
from ....db.models import WritingStyleProfile

router = APIRouter()


# --- Request/Response 스키마 ---

class StyleProfileResponse(BaseModel):
    id: int
    name: str
    blog_id: Optional[str] = None
    crawled_posts_count: int = 0
    is_active: bool = False
    profile_summary: Optional[str] = None  # overall_summary
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# --- API 엔드포인트 ---

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
