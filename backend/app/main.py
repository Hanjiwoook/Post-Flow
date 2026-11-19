import sys
import asyncio

# 최상단에서 가장 먼저 실행되도록 보장 (Playwright/Windows 호환성)
if sys.platform == 'win32':
    print("🔧 [System] Setting Windows ProactorEventLoopPolicy for Playwright...")
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception as e:
        print(f"⚠️ [System] Failed to set event loop policy: {e}")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .api.v1.api import api_router
from .db.session import engine
from .db.base import Base
from .db import models 
from .db.migrate import add_missing_columns

# DB 테이블 생성 + 이미 있는 표에 새 칸 추가 (create_all은 칸을 추가해 주지 않는다)
Base.metadata.create_all(bind=engine)
_added_columns = add_missing_columns(engine, Base.metadata)
if _added_columns:
    print(f"🗄️ [DB] 새 칸 추가: {', '.join(_added_columns)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 실행 중인 루프 종류 확인 (디버깅용)
    try:
        loop = asyncio.get_running_loop()
        print(f"🚀 [System] Server started with loop: {type(loop).__name__}")
    except:
        print("🚀 [System] Server started (Lifespan active)")
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Post Flow API Server",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API"}
