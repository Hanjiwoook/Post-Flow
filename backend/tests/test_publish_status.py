"""
발행 결과 저장과 상태 조회 (6-4) 테스트. 진짜 네이버·진짜 DB 없이 가짜 봇과 메모리 DB로 확인한다.

실행: cd backend → venv/Scripts/python -X utf8 -m unittest discover tests
"""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import JSON, Column, Integer, MetaData, String, Table, create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.migrate import add_missing_columns
from app.db.models import Post
from app.db.session import get_db


def memory_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine)


class FakeBot:
    """naver_automation_v2 대신 쓰는 가짜 봇. 정해 둔 결과를 돌려주고, 단계도 한 번 알린다."""

    def __init__(self, success, login_required=False, last_error="", problems=None, raises=None):
        self.success, self.raises = success, raises
        self.login_required, self.last_error = login_required, last_error
        self.last_problems = problems or []
        self.on_step = None

    def publish(self, *args, **kwargs):
        self.kwargs = kwargs
        if self.on_step:
            self.on_step("글 넣는 중 (1/3)")
        if self.raises:
            raise self.raises
        return self.success


class TestRunPublishJob(unittest.TestCase):
    def setUp(self):
        self.engine, self.Session = memory_db()
        db = self.Session()
        post = Post(title="제목", platform="NAVER", status="PROCESSING")
        db.add(post)
        db.commit()
        self.post_id = post.id
        db.close()

    def run_job(self, bot, tags=None):
        from app.api.v1.endpoints import posts
        steps = []
        original_update = posts._update_post

        def spy_update(post_id, **fields):
            if "step" in fields and fields.get("status") is None:
                steps.append(fields["step"])
            original_update(post_id, **fields)

        with patch("app.db.session.SessionLocal", self.Session), \
                patch.object(posts, "naver_automation_v2", bot), \
                patch.object(posts, "_update_post", spy_update):
            posts.run_publish_job(self.post_id, "제목", [], [], [], {}, "NAVER", None, tags=tags)
        db = self.Session()
        post = db.get(Post, self.post_id)
        db.close()
        return post, steps

    def test_tags_go_to_bot(self):
        bot = FakeBot(True)
        self.run_job(bot, tags=["하남맛집", "초마"])
        self.assertEqual(bot.kwargs.get("tags"), ["하남맛집", "초마"])

    def test_success_keeps_problems(self):
        # 자가 검사에 고칠 것이 있어도 임시저장은 됐으므로 성공 + 고칠 것 목록
        post, steps = self.run_job(FakeBot(True, problems=["3번 블록 정렬이 왼쪽입니다"]))
        self.assertEqual(post.status, "SUCCESS")
        self.assertEqual(post.problems, ["3번 블록 정렬이 왼쪽입니다"])
        self.assertIsNone(post.error_code)
        self.assertIsNone(post.step)  # 끝나면 단계는 지운다
        self.assertEqual(steps, ["글 넣는 중 (1/3)"])  # 진행 중에는 단계가 DB에 적혔다

    def test_login_required(self):
        post, _ = self.run_job(FakeBot(False, login_required=True, last_error="저장된 네이버 로그인이 만료됐습니다"))
        self.assertEqual(post.status, "FAIL")
        self.assertEqual(post.error_code, "LOGIN_REQUIRED")
        self.assertEqual(post.fail_reason, "저장된 네이버 로그인이 만료됐습니다")

    def test_other_failure_has_reason(self):
        post, _ = self.run_job(FakeBot(False, last_error=""))
        self.assertEqual(post.error_code, "PUBLISH_ERROR")
        self.assertTrue(post.fail_reason)  # 이유를 모르더라도 빈 칸으로 두지 않는다

    def test_unexpected_exception_does_not_leave_processing(self):
        # 예외로 멈추면 PROCESSING으로 남아 앱이 끝없이 기다린다
        post, _ = self.run_job(FakeBot(False, raises=RuntimeError("브라우저가 닫혔습니다")))
        self.assertEqual(post.status, "FAIL")
        self.assertIn("브라우저가 닫혔습니다", post.fail_reason)


class TestStatusEndpoint(unittest.TestCase):
    def setUp(self):
        from app.main import app
        self.engine, self.Session = memory_db()
        self.app = app

        def override():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_status_of_failed_post(self):
        db = self.Session()
        post = Post(title="제목", platform="NAVER", status="FAIL", error_code="LOGIN_REQUIRED",
                    fail_reason="저장된 네이버 로그인이 만료됐습니다", problems=None)
        db.add(post)
        db.commit()
        post_id = post.id
        db.close()

        body = self.client.get(f"/api/v1/posts/{post_id}/status").json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["status"], "FAIL")
        self.assertEqual(body["data"]["error_code"], "LOGIN_REQUIRED")
        self.assertEqual(body["data"]["problems"], [])  # 예전 글처럼 비어 있어도 목록으로 준다

    def test_unknown_post(self):
        body = self.client.get("/api/v1/posts/9999/status").json()
        self.assertFalse(body["success"])

    def test_history_still_works(self):
        # /{post_id}/status를 추가해도 /history 경로가 가려지지 않는다
        self.assertEqual(self.client.get("/api/v1/posts/history").status_code, 200)


class TestAddMissingColumns(unittest.TestCase):
    def test_adds_only_missing_columns_and_keeps_rows(self):
        engine = create_engine("sqlite://", poolclass=StaticPool)
        old = MetaData()
        Table("posts", old, Column("id", Integer, primary_key=True), Column("title", String))
        old.create_all(engine)
        with engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO posts (id, title) VALUES (1, '예전 글')")

        new = MetaData()
        Table("posts", new, Column("id", Integer, primary_key=True), Column("title", String),
              Column("step", String), Column("problems", JSON))
        self.assertEqual(add_missing_columns(engine, new), ["posts.step", "posts.problems"])
        self.assertEqual(add_missing_columns(engine, new), [])  # 두 번째에는 할 일 없음

        cols = {c["name"] for c in inspect(engine).get_columns("posts")}
        self.assertEqual(cols, {"id", "title", "step", "problems"})
        with engine.connect() as conn:
            self.assertEqual(conn.exec_driver_sql("SELECT title, step FROM posts").fetchall(), [("예전 글", None)])


if __name__ == "__main__":
    unittest.main()
