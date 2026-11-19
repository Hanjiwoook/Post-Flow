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
    
    # Claude AI
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    # 용도별 모델. .env에서 CLAUDE_MODEL_WRITER=claude-sonnet-5-5 처럼 바꿀 수 있다.
    CLAUDE_MODEL_DEFAULT: str = os.getenv("CLAUDE_MODEL_DEFAULT", "claude-opus-5-5")
    CLAUDE_MODELS: dict = {
        "writer": os.getenv("CLAUDE_MODEL_WRITER", ""),    # 글쓰기 (사진 + 가게 정보)
        # 검토·보강 고쳐쓰기는 Sonnet으로 시작 (11/13 사용자 결정, 비교 결과 충분)
        "reviewer": os.getenv("CLAUDE_MODEL_REVIEWER", "claude-sonnet-5-5"),  # 파워블로거 검토
        "reviser": os.getenv("CLAUDE_MODEL_REVISER", "claude-sonnet-5-5"),   # 검토 반영 고쳐쓰기
        # 가게 정보 요약은 지도 글자를 칸에 옮겨 적는 일이라 Haiku로 충분 (11/18 사용자 결정, Opus는 1회 약 $0.07)
        "summary": os.getenv("CLAUDE_MODEL_SUMMARY", "claude-haiku-5-5"),
    }

    # Branding
    BLOG_NAME: str = os.getenv("BLOG_NAME", "ohuks")
    BLOG_NICKNAME: str = os.getenv("BLOG_NICKNAME", "욱")

    # 글 마지막 줄 고정 감사 인사 (블로그 원문 문구라 저장소에 적지 않고 .env에 둔다)
    BLOG_CLOSING_PHRASE: str = os.getenv("BLOG_CLOSING_PHRASE", "")

    # 기준 블로그 (크롤러·형식 연구 대상, 스타일 프로필의 출처)
    GF_BLOG_ID: str = os.getenv("GF_BLOG_ID", "")

    # Naver Automation
    NAVER_ID: str = os.getenv("NAVER_ID")
    NAVER_PW: str = os.getenv("NAVER_PW")
    NAVER_BLOG_ID: str = os.getenv("NAVER_BLOG_ID")

    # Database (SQLite)
    SQLITE_URL: str = f"sqlite:///{os.path.join(BASE_DIR, 'postflow.db')}"

settings = Settings()
