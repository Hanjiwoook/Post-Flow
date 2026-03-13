from sqlalchemy import Column, Integer, String, DateTime, JSON
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
