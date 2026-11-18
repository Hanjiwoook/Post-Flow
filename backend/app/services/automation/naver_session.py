"""
네이버 로그인 상태 저장.

봇이 매번 아이디·비밀번호로 자동 로그인하면 네이버 보안 확인(새 기기, 캡차)에 걸린다.
그래서 사람이 브라우저 창에서 한 번 직접 로그인하고, 그 로그인 상태(쿠키)를 파일로 저장해 둔다.
발행 봇(naver_v2.py)은 이 파일로 로그인된 채 시작한다.

⚠️ SESSION_PATH 파일은 로그인된 계정 그 자체와 같다. 절대 커밋하거나 공유하지 않는다 (.gitignore 등록).

실행: cd backend → venv/Scripts/python -m app.services.automation.naver_session
"""
import os
import time

from playwright.sync_api import sync_playwright

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SESSION_PATH = os.path.join(BACKEND_DIR, ".naver_session.json")
LOGIN_URL = "https://nid.naver.com/nidlogin.login"
LOGIN_COOKIES = {"NID_AUT", "NID_SES"}  # 로그인하면 생기는 네이버 쿠키
LOGIN_WAIT_SEC = 300


def is_login_page(url: str) -> bool:
    """로그인 페이지(또는 로그인 확인 단계)로 돌려보내졌는지."""
    return "nid.naver.com" in (url or "")


def has_login_cookies(cookies: list) -> bool:
    names = {c.get("name") for c in cookies}
    return LOGIN_COOKIES <= names


def save_login_session(timeout_sec: int = LOGIN_WAIT_SEC) -> bool:
    """브라우저를 띄워 사람이 직접 로그인하게 하고, 로그인되면 상태를 저장한다."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.goto(LOGIN_URL)
        print(f"🔐 열린 창에서 네이버에 직접 로그인해 주세요 (최대 {timeout_sec // 60}분).")
        print("   '로그인 상태 유지'를 체크하면 저장한 로그인이 더 오래 유지됩니다.")
        deadline = time.time() + timeout_sec
        try:
            while time.time() < deadline:
                if has_login_cookies(context.cookies()) and not is_login_page(page.url):
                    # 로그인 직후 네이버가 여러 페이지로 넘어가는 중에 저장하면 'Execution context was destroyed'
                    # 에러가 난다 (11/18). 페이지가 다 열릴 때까지 기다리고, 그래도 넘어가는 중이면 다음 바퀴에 다시 한다.
                    try:
                        page.wait_for_load_state("load", timeout=10000)
                        context.storage_state(path=SESSION_PATH)
                    except Exception:
                        time.sleep(2)
                        continue
                    print("✅ 로그인 상태를 저장했습니다. 이제 발행 봇이 이 로그인으로 시작합니다.")
                    return True
                time.sleep(2)
            print("❌ 시간 안에 로그인하지 못했습니다. 다시 실행해 주세요.")
            return False
        finally:
            browser.close()


if __name__ == "__main__":
    save_login_session()
