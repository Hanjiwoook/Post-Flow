"""
WritingStyleService - 저장된 글쓰기 스타일 프로필 읽기

글쓰기(post_writer.py)가 활성 프로필의 예시 글(few_shot_examples)을 말투 참고 문장으로 프롬프트에 넣는다.
프로필은 DB(writing_style_profiles)에 있다. 지금 활성 프로필 = 기준 블로그 글로 만든 프로필.

11/19 (4-5 Gemini 정리): 블로그 글을 Gemini로 분석해 프로필을 새로 만들던 학습 기능
(analyze_style, select_few_shots, learn_from_blog, /style/learn, /style/preview)은 지웠다.
Gemini 크레딧이 소진돼 동작하지 않았고, 지금 프로필로 충분해서다.
다시 필요하면 blog_crawler.py(크롤러, Gemini 불필요)로 글을 모아 새로 만든다.
"""
from typing import Optional

from ..db.models import WritingStyleProfile
from ..db.session import SessionLocal


class WritingStyleService:
    """저장된 스타일 프로필 조회"""

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


# 싱글톤 인스턴스
writing_style_service = WritingStyleService()
