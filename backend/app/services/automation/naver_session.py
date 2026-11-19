"""
네이버 로그인 상태 저장.

봇이 매번 아이디·비밀번호로 자동 로그인하면 네이버 보안 확인(새 기기, 캡차)에 걸린다.
그래서 사람이 브라우저 창에서 한 번 직접 로그인하고, 발행 봇은 그 로그인이 남아 있는 브라우저로 시작한다.

11/19: 로그인 파일(.naver_session.json)에 쿠키만 담아 매번 빈 Chromium에 넣던 방식에서,
실제 Chrome + 고정 프로필 폴더(PROFILE_DIR)를 로그인 저장과 발행 봇이 같이 쓰는 방식으로 바꿨다.
쿠키뿐 아니라 방문 기록·저장소도 남아서 네이버에는 매번 같은 기기로 보이게 하려는 것이다
(보호조치가 줄어드는지는 써 보면서 확인해야 한다).

⚠️ PROFILE_DIR 폴더는 로그인된 계정 그 자체와 같다. 절대 커밋하거나 공유하지 않는다 (.gitignore 등록).
⚠️ 같은 프로필은 브라우저 하나만 열 수 있다. 로그인 저장 중에는 발행하지 않는다.

실행: cd backend → venv/Scripts/python -X utf8 -m app.services.automation.naver_session
"""
import os
import time

from playwright.sync_api import sync_playwright

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
PROFILE_DIR = os.path.join(BACKEND_DIR, ".naver_profile")
LOGIN_URL = "https://nid.naver.com/nidlogin.login"
LOGIN_COOKIES = {"NID_AUT", "NID_SES"}  # 로그인하면 생기는 네이버 쿠키
LOGIN_WAIT_SEC = 300
SAVE_LOGIN_COMMAND = "cd backend → venv/Scripts/python -X utf8 -m app.services.automation.naver_session"


def is_login_page(url: str) -> bool:
    """로그인 페이지(또는 로그인 확인 단계)로 돌려보내졌는지."""
    return "nid.naver.com" in (url or "")


def has_login_cookies(cookies: list) -> bool:
    names = {c.get("name") for c in cookies}
    return LOGIN_COOKIES <= names


def has_lasting_login(cookies: list, now: float = None) -> bool:
    """로그인 쿠키가 창을 닫아도 남는지 (만료 시각이 있는지).

    '로그인 상태 유지'를 체크하지 않으면 로그인 쿠키가 브라우저를 닫을 때 사라지는 쿠키(expires = -1)가 되어,
    프로필에 남지 않는다.
    """
    now = time.time() if now is None else now
    lasting = {c.get("name") for c in cookies if (c.get("expires") or -1) > now}
    return LOGIN_COOKIES <= lasting


def has_saved_login() -> bool:
    """로그인을 저장한 적이 있는지 (프로필 폴더가 있는지). 실제로 아직 유효한지는 글쓰기 화면을 열어 봐야 안다."""
    return os.path.isdir(PROFILE_DIR)


def open_browser(p):
    """로그인 저장과 발행 봇이 같이 쓰는 브라우저 (실제 Chrome + 고정 프로필).

    돌려주는 것은 BrowserContext다. 다 쓰면 context.close()로 닫아야 프로필에 기록이 저장된다.
    """
    return p.chromium.launch_persistent_context(
        PROFILE_DIR,
        channel="chrome",  # Playwright 내장 Chromium 대신 노트북에 깔린 Chrome
        headless=False,
        viewport={"width": 1280, "height": 800},
        args=["--disable-blink-features=AutomationControlled"],  # 자동화 표시(navigator.webdriver) 끄기
        ignore_default_args=["--enable-automation"],  # "자동화된 테스트 소프트웨어" 안내줄 끄기
    )


def first_page(context):
    """프로필 브라우저는 열리면서 빈 탭이 하나 생긴다. 탭을 더 만들지 않고 그 탭을 쓴다."""
    return context.pages[0] if context.pages else context.new_page()


def save_login_session(timeout_sec: int = LOGIN_WAIT_SEC) -> bool:
    """브라우저를 띄워 사람이 직접 로그인하게 하고, 로그인되면 프로필에 남긴 채 닫는다."""
    with sync_playwright() as p:
        context = open_browser(p)
        page = first_page(context)
        page.goto(LOGIN_URL)
        print(f"🔐 열린 창에서 네이버에 직접 로그인해 주세요 (최대 {timeout_sec // 60}분).")
        print("   ⚠️ '로그인 상태 유지'를 꼭 체크해 주세요. 안 하면 창을 닫을 때 로그인이 사라집니다.")
        deadline = time.time() + timeout_sec
        try:
            while time.time() < deadline:
                cookies = context.cookies()
                if has_login_cookies(cookies) and not is_login_page(page.url):
                    # 로그인 직후 네이버가 여러 페이지로 넘어가는 중에 닫지 않도록 페이지가 다 열릴 때까지 기다린다 (11/18).
                    try:
                        page.wait_for_load_state("load", timeout=10000)
                    except Exception:
                        time.sleep(2)
                        continue
                    if not has_lasting_login(context.cookies()):
                        print("❌ 로그인은 됐지만 '로그인 상태 유지'가 꺼져 있어 창을 닫으면 로그인이 사라집니다.")
                        print("   다시 실행해서 '로그인 상태 유지'를 체크하고 로그인해 주세요.")
                        return False
                    print("✅ 로그인을 저장했습니다. 이제 발행 봇이 같은 브라우저 프로필로 시작합니다.")
                    return True
                time.sleep(2)
            print("❌ 시간 안에 로그인하지 못했습니다. 다시 실행해 주세요.")
            return False
        finally:
            context.close()


if __name__ == "__main__":
    save_login_session()
