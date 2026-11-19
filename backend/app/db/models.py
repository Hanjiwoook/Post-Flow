from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from datetime import datetime
from .base import Base

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    template_name = Column(String, nullable=True) # 추가
    content = Column(String, nullable=True) # 본문 추가
    blocks = Column(JSON, nullable=True) # 레고 블록 구조 추가
    image_paths = Column(JSON, nullable=True) # 단순 경로 리스트 (하위 호환)
    images_data = Column(JSON, nullable=True) # 상세 이미지 정보 리스트 (카테고리 포함) 추가
    tags = Column(JSON, nullable=True) # 태그 리스트 추가
    facts = Column(JSON, nullable=True) # 팩트 체크 정보 추가
    platform = Column(String)  # NAVER, TISTORY 등
    status = Column(String)    # SUCCESS, FAIL, PROCESSING 등
    created_at = Column(DateTime, default=datetime.utcnow)
    post_url = Column(String, nullable=True)
    # 발행 결과 (6-4, 11/19). 앱의 발행 결과 창이 /posts/{id}/status로 읽는다.
    step = Column(String, nullable=True)        # 지금 단계 (예: "글 넣는 중 (3/31)")
    error_code = Column(String, nullable=True)  # LOGIN_REQUIRED(로그인 저장 필요) / PUBLISH_ERROR / None
    fail_reason = Column(String, nullable=True) # 실패 이유 (사람이 읽는 문장)
    problems = Column(JSON, nullable=True)      # 저장 전 자가 검사의 '고칠 것' (임시저장은 됨)


class WritingStyleProfile(Base):
    """블로그 글쓰기 스타일 프로필 - 크롤링한 글에서 추출한 말투/톤/구조 패턴 저장"""
    __tablename__ = "writing_style_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)          # 프로필 이름 (예: "기준 블로그 스타일")
    blog_id = Column(String, nullable=True)                  # 크롤링 소스 블로그 ID
    profile_data = Column(JSON, nullable=True)               # 분석된 스타일 프로필 JSON
    sample_texts = Column(JSON, nullable=True)               # 크롤링한 원본 텍스트 리스트
    few_shot_examples = Column(JSON, nullable=True)          # Few-shot용 대표 예시 (2~3개)
    crawled_posts_count = Column(Integer, default=0)         # 수집된 글 수
    is_active = Column(Boolean, default=False)               # 현재 활성 프로필 여부
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
