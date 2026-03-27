🚀 Post Flow (포스트 플로우)
==========================
### 생성형 AI 기반 블로그 포스팅 자동화 시스템 (V2.1)

"사진만 넣으면, AI가 파워 블로거처럼 글을 써줍니다."

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-3.x-02569B?style=flat-square&logo=flutter&logoColor=white)
![AI](https://img.shields.io/badge/AI-Gemini_2.5_Flash-4285F4?style=flat-square&logo=google-gemini&logoColor=white)

📖 프로젝트 소개
----------------
Post Flow는 블로그 운영의 번거로움을 해결하기 위해 개발된 1인 토이 프로젝트입니다. 사용자가 촬영한 사진들을 업로드하면, Google Gemini AI가 사진의 맥락을 분석하여 제목, 본문, 해시태그가 포함된 완벽한 블로그 포스팅 초안을 자동으로 생성해 줍니다. 

단순 초안 생성을 넘어, **Playwright 기반의 V2 엔진**이 네이버 스마트에디터에 직접 접속하여 이미지와 글을 완벽하게 배치(Interleaving)하고 발행까지 100% 자동화합니다.

🎯 핵심 기능
------------
*   **다중 이미지 분석:** 최대 50장의 사진을 한 번에 분석하여 스토리를 연결합니다.
*   **AI 글쓰기 자동화:** 상황에 맞는 감성적인/전문적인 말투로 글을 작성합니다. (인플루언서 모드)
*   **🤖 완전 자동 발행 (V2):** 네이버 스마트에디터 ONE에 접속하여 제목, 본문, 사진(콜라주), 태그까지 완벽하게 입력합니다.
*   **🛡️ 불사조 재시도(Retry) 로직:** 네트워크 지연이나 브라우저 예외 시 최대 3회 자동 재시도를 통해 안정적인 발행을 보장합니다.
*   **🎨 스마트 에디터 UI:** AI 분석 결과물을 실시간으로 수정하고, 사진 카테고리를 직관적으로 이동할 수 있는 에디터를 제공합니다.

🛠️ 기술 스택 (Tech Stack)
--------------------------
### Backend
*   **Language:** Python 3.10+
*   **Framework:** FastAPI
*   **AI Model:** Google Gemini 2.5 Flash
*   **Automation:** Playwright (Stealth Mode), `pyperclip` (Login Bypass)
*   **Database:** SQLite (SQLAlchemy ORM)

### Frontend
*   **Framework:** Flutter (Dart)
*   **State Management:** Provider
*   **UI/UX:** Modern Material 3 (Image Viewer & Pinch-Zoom 지원)

📂 프로젝트 구조 (Monorepo)
--------------------------
```text
post-flow/
├── backend/            # Python FastAPI 서버 & Automation Engine
│   ├── app/            # 메인 애플리케이션 코드
│   │   ├── api/        # API 엔드포인트 (v1)
│   │   ├── core/       # 설정 및 공통 로직
│   │   ├── db/         # 데이터베이스 모델 및 세션
│   │   ├── schemas/    # Pydantic 데이터 모델
│   │   └── services/   # 비즈니스 로직 (AI 에이전트, Playwright 자동화)
│   ├── test_e2e_pipeline.py # E2E 통합 테스트 스크립트
│   ├── .env            # 환경변수 (API Key, 네이버 계정 정보)
│   └── requirements.txt
└── frontend/           # Flutter 앱
    ├── lib/            # 화면 및 상태 관리 코드
    └── pubspec.yaml    
```

🚀 시작 가이드 (Getting Started)
-------------------------------
이 프로젝트를 로컬 환경에서 실행하려면 아래 절차를 따라주세요.

### 1. Backend 실행 (Server)
```bash
# 1. backend 폴더로 이동
cd backend

# 2. 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\Activate # Windows

# 3. 라이브러리 설치
pip install -r requirements.txt

# 4. ⚠️ 중요: 환경 변수 설정 (.env 파일 생성)
# GEMINI_API_KEY, NAVER_ID, NAVER_PW 등 환경 변수 직접 입력

# 5. 서버 실행
python run.py

서버 주소: http://127.0.0.1:8000
Swagger UI: http://127.0.0.1:8000/docs
```

### 2. Frontend 실행 (App)
```bash
cd frontend
flutter pub get
flutter run
```

🧪 테스트 (QA & Automation Testing)
-----------------------------------
단순 기능 검증을 넘어, 시스템의 신뢰성을 보장하는 **SDET 관점의 테스트 환경**을 구축했습니다.

*   ✅ **E2E 파이프라인 테스트 (/test_e2e_pipeline.py):** 이미지 투입부터 AI 분석, 최종 블로그 발행까지 전 과정을 자동 검증합니다.
*   ✅ **브라우저 안정성 테스트:** Playwright 봇의 에러 상황 대처 및 Retry 로직 작동 여부를 검증합니다.
*   ✅ **서버 헬스 체크 & Gemini API 연동 테스트** 완료.

👨‍💻 개발자 (Author)
------------------
**Ji-wook (QA Engineer & Full-stack Developer)**

## 📜 라이선스 (License)
**Copyright (c) 2026 Han Ji-wook. All rights reserved.**  
본 프로젝트의 모든 권리는 저작권자에게 있습니다. 개인 포트폴리오 및 학습용으로만 공개된 코드이며, 저작권자의 허가 없는 **무단 도용, 재배포 및 고의적인 상업적 이용을 엄격히 금지**합니다.

---
이 프로젝트는 AI 기반 수익화 자동화를 목표로 지속적으로 업데이트될 예정입니다.
