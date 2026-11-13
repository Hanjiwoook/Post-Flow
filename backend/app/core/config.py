import os
from dotenv import load_dotenv

# .env 파일 로드
# backend/.env 위치를 찾기 위해 상위 디렉토리로 이동
# 현재 위치: backend/app/core/config.py -> 상위(core) -> 상위(app) -> 상위(backend) -> .env
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Settings:
    PROJECT_NAME: str = "Post Flow"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Gemini AI (Claude로 옮기는 중. 4-5단계에서 제거)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"

    # Claude AI
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    # 용도별 모델. .env에서 CLAUDE_MODEL_WRITER=claude-sonnet-5-5 처럼 바꿀 수 있다.
    CLAUDE_MODEL_DEFAULT: str = os.getenv("CLAUDE_MODEL_DEFAULT", "claude-opus-5-5")
    CLAUDE_MODELS: dict = {
        "writer": os.getenv("CLAUDE_MODEL_WRITER", ""),    # 글쓰기 (사진 + 가게 정보)
        "reviewer": os.getenv("CLAUDE_MODEL_REVIEWER", ""),  # 파워블로거 검토
        "summary": os.getenv("CLAUDE_MODEL_SUMMARY", ""),   # 가게 정보 요약
        "style": os.getenv("CLAUDE_MODEL_STYLE", ""),     # 스타일 학습
        "refine": os.getenv("CLAUDE_MODEL_REFINE", ""),    # AI 부분 수정
    }

    # Branding
    BLOG_NAME: str = os.getenv("BLOG_NAME", "ohuks")
    BLOG_NICKNAME: str = os.getenv("BLOG_NICKNAME", "욱")

    # Style Learning (크롤링 대상 블로그)
    GF_BLOG_ID: str = os.getenv("GF_BLOG_ID", "")

    # Naver Automation
    NAVER_ID: str = os.getenv("NAVER_ID")
    NAVER_PW: str = os.getenv("NAVER_PW")
    NAVER_BLOG_ID: str = os.getenv("NAVER_BLOG_ID")

    # Database (SQLite)
    SQLITE_URL: str = f"sqlite:///{os.path.join(BASE_DIR, 'postflow.db')}"

settings = Settings()
