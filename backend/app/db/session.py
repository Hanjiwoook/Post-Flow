from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .base import Base

# SQLite 데이터베이스 URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./postflow.db"

# 엔진 생성 (SQLite의 경우 check_same_thread를 False로 설정)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 세션 생성기
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DB 세션을 가져오는 의존성 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()