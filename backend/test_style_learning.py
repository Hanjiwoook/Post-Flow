"""
스타일 학습 시스템 테스트 스크립트
서버가 실행 중일 때: python test_style_learning.py api
서버 없이 직접 테스트: python test_style_learning.py direct
"""
import asyncio
import sys
import json

# 직접 테스트용 (.env 로드)
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


async def test_crawler_only(blog_id: str):
    """크롤러만 단독 테스트"""
    from app.services.blog_crawler import blog_crawler
    
    print(f"\n{'='*60}")
    print(f"🧪 크롤러 테스트 - blog_id: '{blog_id}'")
    print(f"{'='*60}")
    
    results = await blog_crawler.crawl_all(blog_id, max_posts=5)
    
    print(f"\n📊 결과 요약:")
    print(f"  수집된 글: {len(results)}편")
    for i, r in enumerate(results):
        preview = r['content'][:100] if r.get('content') else '(내용 없음)'
        print(f"  [{i+1}] {r['title']}")
        print(f"      미리보기: {preview}...")
    
    return results


async def test_full_pipeline(blog_id: str, profile_name: str = "테스트 스타일"):
    """전체 파이프라인 테스트 (크롤링 → 분석 → 저장)"""
    from app.services.writing_style_service import writing_style_service
    
    print(f"\n{'='*60}")
    print(f"🧪 전체 파이프라인 테스트")
    print(f"  blog_id: '{blog_id}'")
    print(f"  profile_name: '{profile_name}'")
    print(f"{'='*60}")
    
    # DB 테이블 생성 확인
    from app.db.session import engine
    from app.db.base import Base
    from app.db import models
    Base.metadata.create_all(bind=engine)
    
    result = await writing_style_service.learn_from_blog(
        blog_id=blog_id,
        profile_name=profile_name,
        max_posts=5
    )
    
    print(f"\n📊 학습 결과:")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    
    # 프로필 로드 테스트
    active = writing_style_service.get_active_profile()
    if active:
        print(f"\n✅ 활성 프로필 로드 성공: '{active['name']}'")
        
        # 프롬프트 생성 테스트
        prompt = writing_style_service.generate_style_prompt(
            active['profile_data'],
            active['few_shot_examples']
        )
        print(f"\n📝 생성된 프롬프트 (처음 500자):")
        print(prompt[:500])
    
    return result


async def test_via_api(blog_id: str):
    """서버 API를 통한 테스트"""
    import httpx
    
    base_url = "http://localhost:8000/api/v1"
    
    print(f"\n{'='*60}")
    print(f"🧪 API 테스트 - blog_id: '{blog_id}'")
    print(f"{'='*60}")
    
    async with httpx.AsyncClient(timeout=300) as client:
        # 1. 스타일 학습
        print("\n📡 [1/3] POST /style/learn")
        resp = await client.post(f"{base_url}/style/learn", json={
            "blog_id": blog_id,
            "profile_name": "여친 스타일",
            "max_posts": 5
        })
        print(f"  Status: {resp.status_code}")
        data = resp.json()
        print(f"  Message: {data.get('message')}")
        
        if not data.get('success'):
            print(f"  ❌ Error: {data.get('error')}")
            return
        
        # 2. 프로필 목록 조회
        print("\n📡 [2/3] GET /style/profiles")
        resp = await client.get(f"{base_url}/style/profiles")
        profiles = resp.json().get('data', [])
        for p in profiles:
            active_mark = "🟢" if p.get('is_active') else "⚪"
            print(f"  {active_mark} [{p['id']}] {p['name']} ({p.get('crawled_posts_count', 0)}편)")
        
        # 3. 스타일 미리보기
        print("\n📡 [3/3] POST /style/preview")
        resp = await client.post(f"{base_url}/style/preview", json={
            "sample_text": "오늘 남자친구랑 홍대에 새로 생긴 라멘집에 갔다."
        })
        preview_data = resp.json()
        if preview_data.get('success'):
            print(f"  원본: {preview_data['data']['original']}")
            print(f"  변환: {preview_data['data']['styled']}")
        else:
            print(f"  ❌ {preview_data.get('message')}")
    
    print(f"\n✅ API 테스트 완료!")


if __name__ == "__main__":
    blog_id = os.getenv("GF_BLOG_ID", "")
    
    if not blog_id:
        print("❌ GF_BLOG_ID가 설정되지 않았습니다.")
        print("   .env 파일에 GF_BLOG_ID=블로그아이디 를 추가하거나,")
        print("   명령어: python test_style_learning.py direct 블로그아이디")
        sys.exit(1)
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "direct"
    
    # 인자로 blog_id 오버라이드
    if len(sys.argv) > 2:
        blog_id = sys.argv[2]
    
    if mode == "crawler":
        asyncio.run(test_crawler_only(blog_id))
    elif mode == "direct":
        asyncio.run(test_full_pipeline(blog_id))
    elif mode == "api":
        asyncio.run(test_via_api(blog_id))
    else:
        print(f"사용법: python test_style_learning.py [crawler|direct|api] [blog_id]")
