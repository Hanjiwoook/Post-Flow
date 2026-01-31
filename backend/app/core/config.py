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
    
    # Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL_NAME: str = "gemini-2.5-flash"

    # Database (SQLite)
    SQLITE_URL: str = f"sqlite:///{os.path.join(BASE_DIR, 'postflow.db')}"

settings = Settings()
