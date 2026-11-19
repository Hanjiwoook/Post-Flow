"""
네이버 로그인 상태 판단 함수 테스트 (브라우저 없이).

실행: cd backend → venv/Scripts/python -m unittest discover tests
"""
import os
import unittest

from app.services.automation.naver_session import PROFILE_DIR, has_lasting_login, has_login_cookies, is_login_page


class TestLoginState(unittest.TestCase):
    def test_login_page_detection(self):
        self.assertTrue(is_login_page("https://nid.naver.com/nidlogin.login?mode=form"))
        self.assertTrue(is_login_page("https://nid.naver.com/login/ext/deviceConfirm"))  # 로그인 확인 단계도 로그인 전
        self.assertFalse(is_login_page("https://blog.naver.com/someone?Redirect=Write&"))
        self.assertFalse(is_login_page(""))

    def test_login_cookies_need_both(self):
        self.assertTrue(has_login_cookies([{"name": "NID_AUT"}, {"name": "NID_SES"}, {"name": "x"}]))
        self.assertFalse(has_login_cookies([{"name": "NID_AUT"}]))
        self.assertFalse(has_login_cookies([]))

    def test_lasting_login_needs_expiry_on_both_cookies(self):
        # '로그인 상태 유지'를 안 하면 쿠키가 expires=-1(창을 닫으면 사라짐)이라 프로필에 남지 않는다
        now = 1_000_000
        later = now + 86400
        self.assertTrue(has_lasting_login([{"name": "NID_AUT", "expires": later}, {"name": "NID_SES", "expires": later}], now))
        self.assertFalse(has_lasting_login([{"name": "NID_AUT", "expires": later}, {"name": "NID_SES", "expires": -1}], now))
        self.assertFalse(has_lasting_login([{"name": "NID_AUT", "expires": now - 1}, {"name": "NID_SES", "expires": later}], now))
        self.assertFalse(has_lasting_login([], now))

    def test_profile_dir_is_inside_backend(self):
        # .gitignore의 backend/.naver_profile/ 과 경로가 같아야 커밋되지 않는다
        self.assertEqual(os.path.basename(PROFILE_DIR), ".naver_profile")
        self.assertEqual(os.path.basename(os.path.dirname(PROFILE_DIR)), "backend")

if __name__ == "__main__":
    unittest.main()
