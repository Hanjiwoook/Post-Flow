# Post Flow

**사진과 가게 정보를 넣으면 AI가 정해진 형식의 맛집 블로그 글을 쓰고, 봇이 네이버 블로그 편집기에 그대로 입력해 임시저장까지 해 주는 도구**

![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-3.22-02569B?style=flat-square&logo=flutter&logoColor=white)
![Claude API](https://img.shields.io/badge/AI-Claude_API-D97757?style=flat-square)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=flat-square&logo=playwright&logoColor=white)

<!-- 📸 대표 화면 캡처: docs/images/overview.png (편집 화면 + 작성 리포트가 보이게) -->
<!-- ![Post Flow 화면](docs/images/overview.png) -->

## 왜 만들었나

맛집 블로그 글은 매번 형식이 같습니다. 가게 이름 인용구, 지도, 사진 2장 묶음과 짧은 설명, 메뉴별 맛 묘사, 가게 정보, 맺음말 순서입니다. 사진 고르기, 순서 맞추기, 편집기에서 인용구 스타일·글씨 크기·정렬을 하나하나 맞추는 데 시간이 많이 듭니다.

Post Flow는 이 반복 작업을 맡습니다. 사람은 **노트북 앱에서 글을 읽고 확인한 뒤 발행만** 합니다.

- 자동으로 하는 일: 글쓰기, 사진 고르기, 형식 검사, 검수, 편집기 입력, 임시저장
- 사람이 하는 일: 내용 확인, 사람 얼굴 모자이크, 최종 발행 버튼

## 동작 흐름

```mermaid
flowchart LR
    A[사진 + 가게 정보 + 메모] --> B[AI 글쓰기<br/>Claude Opus]
    B --> C[작성 리포트<br/>형식 검사 · 뺀 사진 · 확인 필요]
    C --> D[검수 에이전트<br/>Claude Sonnet]
    D -->|고쳐쓰기 1회| C
    C --> E[발행 봇<br/>Playwright]
    E --> F[저장 전 자가 검사]
    F --> G[네이버 임시저장]
    G --> H[사람이 확인하고 발행]
```

1. **가게 정보 가져오기:** 네이버 지도에서 영업시간·주소·리뷰를 가져와 Claude Haiku가 칸별로 정리합니다.
2. **글쓰기:** 사진 전부와 가게 정보, 형식 지시문을 한 번에 넣어 Claude Opus가 블록(글, 사진 묶음, 인용구, 지도) 단위로 씁니다.
3. **작성 리포트:** 형식 검사 결과, 뺀 사진과 그 이유, 사실 확인이 필요한 부분을 앱에 보여 줍니다.
4. **검수:** "파워블로거 시선"의 검수 에이전트가 점수와 지적, 사용자에게 물을 질문을 돌려줍니다. 답을 넣으면 한 번 고쳐 씁니다.
5. **발행 봇:** 저장된 로그인으로 편집기를 열어 블록 순서대로 입력하고, 저장 직전 편집기 HTML을 초안과 비교한 뒤 임시저장합니다.
6. **발행 결과 창:** 진행 단계, 자가 검사의 "고칠 것", 실패 이유를 앱에 보여 줍니다.

<!-- 📸 화면 캡처 자리 (넣을 때 주석을 풀어 주세요)
| 홈 (사진·가게 정보) | 편집 화면 · 작성 리포트 | 검수 결과 | 발행 결과 |
|---|---|---|---|
| ![](docs/images/home.png) | ![](docs/images/editor.png) | ![](docs/images/review.png) | ![](docs/images/publish_result.png) |
-->

## 주요 기능

### 글쓰기 (`services/post_writer.py`, `prompt_builder.py`)
- 기준 블로그 글의 **형식만** 따르고, 내용은 사진·가게 정보·사용자 메모에 근거해 씁니다. 근거가 없는 만족도·재방문 의사는 쓰지 않고 "확인 필요"로 돌립니다.
- **필요한 사진만 골라 씁니다.** 뺀 사진은 이유와 함께 보여 주고, 앱에서 다시 넣을 수 있습니다.
- 영수증 사진은 카드번호 같은 개인정보가 보여서 **코드로** 글에서 뺍니다(AI 판단에만 맡기지 않음).
- 비슷한 연사 사진은 Pillow만으로 만든 dHash로 묶어 AI에게 힌트로 줍니다(`photo_dedup.py`).
- 사진 번호의 범위·중복·누락은 AI 응답을 받은 뒤 코드로 다시 검증합니다.

### 형식 검사기 (`services/format_checker.py`)
- 기준 블로그의 실제 글 5편에서 잰 값으로 규칙을 만들었습니다. 실제 글 5편은 모두 통과합니다.
- 예: 줄 끝 마침표 비율, 폰에서 꺾이는 줄(20자 초과) 비율, 이모지 위치, 같은 끝맺음 반복, AI가 자주 쓰는 표현("풍미", "조화를 이루" 등), 협찬 글 표시.

### 검수와 고쳐쓰기 (`post_reviewer.py`, `post_reviser.py`)
- 6개 기준의 점수, 블록 위치가 표시된 지적, 사용자에게 물을 질문(예시 답 포함)을 돌려줍니다.
- 검수 에이전트는 글을 직접 고치지 않습니다. 사실이 필요한 보강은 사용자에게 질문으로 돌립니다. 고쳐쓰기는 한 번만 합니다.

### 발행 봇 (`services/automation/naver_v2.py`)
- 지도 블록, 인용구 스타일, 사진 콜라주, 글씨 크기 15·가운데 정렬, 블록 사이 간격을 기준 블로그 서식에 맞춥니다.
- **저장 전 자가 검사(`editor_check.py`):** 블록 순서, 줄, 빈 줄, 정렬, 글씨 크기, 사진 장수, 지도를 초안과 비교합니다. 문제가 있어도 임시저장은 하고, "고칠 것"으로 알려 줍니다.
- 글에 없는 사진은 올리지 않습니다. `publish(save=False)` 시험 모드는 저장 버튼을 누르지 않습니다.

## 기술 스택

| 구분 | 사용 |
|---|---|
| Backend | Python 3.10, FastAPI, SQLAlchemy(SQLite), Pydantic |
| AI | Claude API (`anthropic` SDK, 구조화된 출력) |
| 자동화 | Playwright(Chrome), playwright-stealth, httpx + BeautifulSoup(크롤링) |
| Frontend | Flutter 3.22 (Windows 앱), Provider |

**용도별 모델** (`core/config.py`, `.env`에서 바꿀 수 있음)

| 용도 | 모델 | 이유 |
|---|---|---|
| 글쓰기 | Claude Opus | 사진 판단과 형식 지키기가 가장 중요해서 |
| 검수·고쳐쓰기 | Claude Sonnet | 같은 초안으로 비교했을 때 충분했고, 토큰 가격이 Opus의 절반 |
| 가게 정보 정리 | Claude Haiku | 지도 글자를 칸에 옮기는 일이라 Opus와 주요 칸 결과가 같았음 |

## 설계 결정과 문제 해결

### 1. "저장을 눌렀다"는 성공이 아니었다 → 저장 전 자가 검사
봇이 저장까지 마쳤는데도, 정렬과 글씨 크기가 적용되지 않은 글이 있었습니다. 저장 직전 편집기 HTML을 손으로 초안과 비교하고 나서야 알았습니다. 그래서 이 비교를 코드로 만들었습니다(`editor_check.py`). 다시 돌리면 같은 글이 중복으로 임시저장되기 때문에, 문제가 있어도 실패로 처리하지 않고 "고칠 것" 목록으로 돌려줍니다.

### 2. 네이버 보안 확인 → 저장된 로그인 + 고정 Chrome 프로필
매번 아이디·비밀번호로 자동 로그인하면 네이버 보안 확인에 걸려 글쓰기 화면이 로그인 페이지로 돌아갔습니다. 지금은 사람이 한 번 직접 로그인하고, 봇과 로그인 저장이 **같은 Chrome 프로필**을 씁니다. 로그인이 만료되면 다시 시도해도 같은 결과이고 의심 기록만 쌓이므로 **재시도하지 않고** 앱에 로그인 저장 방법을 안내합니다.

### 3. 3장 이상 콜라주의 사진이 사라졌다 → 업로드 완료를 직접 확인
4장 콜라주를 넣으면 2장만 남는 문제가 있었습니다. 단계마다 사진 수를 세어 보니, 업로드 중인 사진은 `data:` 미리보기였다가 서버에 올라가면 `http` 주소로 바뀌었습니다. 그런데 편집기는 **화면에 보이지 않는 칸의 업로드를 마무리하지 않았습니다.** 콜라주 윗줄이 화면 위로 밀리면 그 사진이 미리보기에서 멈췄습니다. 지금은 업로드하는 동안 그 칸을 화면에 보이게 두고, `http` 주소로 바뀐 사진만 셉니다. 자가 검사도 미리보기만 있는 사진을 잡습니다. 같은 조사에서, 콜라주 선택이 버튼이 아니라 "화면 가운데 클릭"이 우연히 맞아서 되던 것도 찾아 고쳤습니다.

### 4. 실패를 숨기던 AI 호출 → Claude API로 옮기고 실패를 드러내기
예전 Gemini 코드는 크레딧이 떨어져 호출이 실패해도 `except: return {}`로 빈 결과와 "성공"을 돌려줬습니다. Claude API로 옮기면서 실패는 한국어 오류 메시지로 앱에 알리고, 실패한 호출도 청구되므로 사용량을 먼저 기록하도록 했습니다.

### 5. 글쓰기 비용이 약 1.5배가 됐다 → 원인부터 측정
같은 사진으로 쓴 글의 비용이 $0.24에서 $0.35로 늘었습니다. 무료 토큰 세기 API로 보이는 응답의 토큰을 세어 보니, 늘어난 출력의 대부분은 AI가 속으로 생각하는 데 쓴 토큰이었습니다(약 3,700 → 7,800, 추정). 생각을 줄이는 설정(effort low)은 절약액(편당 약 $0.08)에 비해 품질 위험이 커서 적용하지 않았습니다. 대신 생각 토큰을 응답 사용량에 따로 기록해 앞으로 바로 볼 수 있게 했습니다.

## 비용과 시간 (실측)

같은 가게 사진 20장으로 측정한 값입니다. 토큰 수로 계산한 **추정 비용**이며, 실행할 때마다 달라집니다.

| 단계 | 모델 | 비용(1회) | 시간 |
|---|---|---|---|
| 가게 정보 정리 | Haiku | 약 $0.0015 | (기록 없음) |
| 글쓰기 | Opus | 약 $0.33~0.35 | 약 2분 |
| 검수 | Sonnet | 약 $0.045~0.057 | 약 25~35초 |
| 고쳐쓰기 | Sonnet | 약 $0.04~0.047 | 약 15초 |
| 발행 봇 | (AI 없음) | 0 | 사진 수에 따라 수 분 |

## 프로젝트 구조

```text
post-flow/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # posts(글쓰기·검수·발행·상태), system(가게 정보), style(스타일 프로필)
│   │   ├── services/
│   │   │   ├── post_writer.py      # 글쓰기 (Claude 1회 호출)
│   │   │   ├── prompt_builder.py   # 형식 지시문
│   │   │   ├── format_checker.py   # 형식 검사기
│   │   │   ├── post_reviewer.py    # 검수 에이전트
│   │   │   ├── post_reviser.py     # 고쳐쓰기
│   │   │   ├── place_summarizer.py # 가게 정보 정리
│   │   │   ├── photo_dedup.py      # 연사 묶기
│   │   │   ├── llm_client.py       # Claude 호출, 오류 메시지, 사용량 기록
│   │   │   ├── blog_crawler.py     # 기준 블로그 글을 블록 단위로 크롤링
│   │   │   └── automation/
│   │   │       ├── naver_v2.py       # 발행 봇
│   │   │       ├── editor_check.py   # 저장 전 자가 검사
│   │   │       └── naver_session.py  # 로그인 저장 (Chrome 프로필)
│   │   ├── db/                  # 모델, 기존 DB에 새 칸 추가(migrate.py)
│   │   └── schemas/
│   ├── tests/                   # unittest
│   └── run.py
├── frontend/lib/
│   ├── screens/                 # 홈, 편집, 검수
│   ├── widgets/                 # 작성 리포트 카드, 발행 결과 창
│   ├── providers/               # PostProvider
│   └── services/api_service.dart
└── docs/blog_format_spec.md     # 글 형식 명세서
```

## 실행 방법

### 1. 백엔드
```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
playwright install chrome        # 발행 봇이 실제 Chrome을 쓴다
```

`backend/.env`를 만들고 아래 항목을 채웁니다(값은 저장소에 올리지 않습니다).

| 이름 | 설명 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API 키 |
| `NAVER_BLOG_ID` | 임시저장할 네이버 블로그 ID |
| `BLOG_CLOSING_PHRASE` | 글 끝 감사 인사 문구 |
| `GF_BLOG_ID` | (선택) 형식 기준 블로그 ID, 크롤러용 |
| `CLAUDE_MODEL_WRITER` 등 | (선택) 용도별 모델 바꾸기 |

```bash
python run.py                    # http://127.0.0.1:8000/docs
```

### 2. 네이버 로그인 저장 (처음 한 번, 만료됐을 때)
```bash
cd backend
venv/Scripts/python -X utf8 -m app.services.automation.naver_session
```
열린 Chrome 창에서 직접 로그인합니다. **'로그인 상태 유지'를 체크해야** 저장됩니다. 로그인은 `backend/.naver_profile/`에 저장되며 git에 올라가지 않습니다.

### 3. 앱
```bash
cd frontend
flutter pub get
flutter run -d windows
```

## 테스트

```bash
cd backend && venv/Scripts/python -X utf8 -m unittest discover tests   # 176개
cd frontend && flutter test                                            # 24개
```

- **AI 호출:** 가짜 클라이언트로 응답 형식, 오류 처리, 거절·길이 초과, 사용량 기록을 검증합니다. 테스트는 비용을 쓰지 않습니다.
- **형식 검사기:** 실제 글 5편이 통과하는지, 규칙별 위반 예시를 잡는지 검증합니다.
- **발행 봇:** 편집기 HTML을 흉내 낸 가짜 HTML로 자가 검사를, 가짜 편집기로 콜라주 선택·업로드 대기·재시도 횟수를 검증합니다.
- **발행 결과:** 메모리 DB로 결과 저장과 상태 API를, Flutter 위젯 테스트로 결과 창을 검증합니다.
- **실제 편집기:** 테스트로 확인할 수 없는 부분은 시험 모드(`save=False`)로 실제 편집기에 입력한 뒤 자가 검사 결과를 봅니다.

## 한계

- 네이버 편집기 화면 구조가 바뀌면 봇이 깨질 수 있습니다. 자가 검사가 대부분 잡아내지만, 고치는 것은 사람의 몫입니다.
- 맛집 글 형식만 지원합니다.
- 발행은 임시저장까지만 자동입니다. 사람이 확인하고 발행합니다.
- 비용은 사진 수와 글 길이에 따라 달라지며, 위 표는 한 가게로 잰 값입니다.

## 개발자

**Han Ji-wook (한지욱)**

## 라이선스

Copyright (c) 2026 Han Ji-wook. All rights reserved.
개인 포트폴리오 및 학습용으로 공개한 코드입니다. 저작권자의 허가 없는 무단 도용, 재배포, 상업적 이용을 금지합니다. 자세한 내용은 [LICENSE](LICENSE)를 참고해 주세요.
