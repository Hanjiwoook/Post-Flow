# 🚀 Post Flow (포스트 플로우)

**생성형 AI 기반 블로그 포스팅 자동화 시스템**
> "사진만 넣으면, AI가 파워 블로거처럼 글을 써줍니다."

![Project Status](https://img.shields.io/badge/Status-MVP_Completed-green)
![Python](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)
![Flutter](https://img.shields.io/badge/Frontend-Flutter-02569B?logo=flutter)
![AI](https://img.shields.io/badge/AI-Gemini_2.5_Flash-4285F4?logo=google-gemini)

## 📖 프로젝트 소개
**Post Flow**는 블로그 운영의 번거로움을 해결하기 위해 개발된 1인 토이 프로젝트입니다.
사용자가 촬영한 사진들을 업로드하면, Google Gemini AI가 사진의 맥락을 분석하여 **제목, 본문, 해시태그**가 포함된 완벽한 블로그 포스팅 초안을 자동으로 생성해 줍니다.

### 🎯 핵심 기능
- **다중 이미지 분석:** 최대 10장의 사진을 한 번에 분석하여 스토리를 연결합니다.
- **AI 글쓰기 자동화:** 상황에 맞는 감성적인/전문적인 말투로 글을 작성합니다.
- **구조화된 출력:** 제목, 본문, 추천 태그를 깔끔하게 분리하여 제공합니다.

---

## 🛠️ 기술 스택 (Tech Stack)

### Backend
- **Language:** Python 3.10+
- **Framework:** FastAPI
- **AI Model:** Google Gemini 2.5 Flash
- **Libraries:** Pillow (이미지 처리), Uvicorn (ASGI 서버)

### Frontend
- **Framework:** Flutter (Dart)
- **Http Client:** http package
- **State Management:** Stateful Widget (Basic)

---

## 📂 프로젝트 구조 (Monorepo)

```bash
post-flow/
├── backend/            # Python FastAPI 서버
│   ├── .env            # 환경변수 (API Key - 직접 생성 필요)
│   └── main.py         # 서버 메인 코드
└── frontend/           # Flutter 앱
    ├── lib/
    │   └── main.dart   # 앱 메인 화면 코드
    └── pubspec.yaml    # 플러터 설정 파일
```

---

## 🚀 시작 가이드 (Getting Started)

이 프로젝트를 로컬 환경에서 실행하려면 아래 절차를 따라주세요.

### 1. Backend 실행 (Server)

```bash
# 1. backend 폴더로 이동
cd backend

# 2. 가상환경 생성 및 활성화
python -m venv venv
# Windows:
.\venv\Scripts\Activate
# Mac/Linux:
source venv/bin/activate

# 3. 라이브러리 설치
pip install -r requirements.txt
# (또는) pip install fastapi "uvicorn[standard]" google-generativeai pillow python-dotenv

# 4. ⚠️ 중요: 환경 변수 설정 (.env 파일 생성)
# backend 폴더 안에 .env 파일을 직접 만들고 아래 내용을 입력하세요.
# (보안을 위해 .env 파일은 Git에 포함되지 않습니다.)
GEMINI_API_KEY=당신의_구글_API_키_입력

# 5. 서버 실행
uvicorn main:app --reload
```

- **서버 주소:** `http://127.0.0.1:8000`
- **Swagger UI:** `http://127.0.0.1:8000/docs`

### 2. Frontend 실행 (App)

새로운 터미널을 열어서 진행하세요.

```bash
# 1. frontend 폴더로 이동
cd frontend

# 2. 의존성 패키지 설치
flutter pub get

# 3. 앱 실행
flutter run
```

---

## 🧪 테스트 (QA Testing)

현재 MVP(Minimum Viable Product) 단계의 기능 검증이 완료되었습니다.

- [x] 서버 헬스 체크 (`/health`)
- [x] Gemini API 연동 테스트 (`/test-ai`)
- [x] 이미지 업로드 및 분석 기능 (`/api/v1/analyze`)
- [x] 플러터 앱 UI 연동

---

## 👨‍💻 개발자 (Author)

**Ji-wook** (QA Engineer & Full-stack Developer)

> 이 프로젝트는 AI 기반 수익화 자동화를 목표로 지속적으로 업데이트될 예정입니다.
