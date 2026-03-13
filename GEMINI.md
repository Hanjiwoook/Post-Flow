# Post Flow 프로젝트 컨텍스트

이 파일은 Gemini CLI가 프로젝트의 맥락을 빠르게 파악하기 위한 가이드라인입니다.

## 🛠️ 기술 스택
- **Backend:** FastAPI (Python), Playwright (Browser Automation), Google Gemini API (AI Analysis)
- **Frontend:** Flutter (Dart), Provider (State Management)
- **Database:** SQLite (SQLAlchemy ORM)

## 🏗️ 아키텍처 및 핵심 워크플로우
1. **이미지 분석:** `GeminiService`가 이미지를 분류하고 블로그 초안을 생성함.
2. **블록 에디팅:** `ContentBlock` JSON 구조를 통해 프론트-백엔드 간 콘텐츠 교환.
3. **자동 발행:** `NaverBlogAutomationV2` (Playwright)를 사용해 네이버 블로그 포스팅 자동 수행.
4. **비동기 처리:** `BackgroundTasks`를 이용해 포스팅 발행 프로세스 관리.

## 📝 작업 원칙
- 모든 백엔드 코드는 `backend/` 디렉토리에, 프론트엔드는 `frontend/`에 위치함.
- 네이버 블로그 발행 시 Windows 환경의 `ProactorEventLoopPolicy` 호환성을 유지해야 함.
- 새로운 기능을 추가할 때는 `TODO.md`나 `DAILY_REPORT/`를 참고하여 맥락을 이어감.
