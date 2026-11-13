"""
llm_client 단위 테스트. 실제 Claude API를 부르지 않고 가짜 클라이언트를 쓴다 (비용 0).

실행: cd backend → venv\\Scripts\\python -m unittest discover tests
"""
import base64
import io
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx2
from PIL import Image
from pydantic import BaseModel

from app.core.config import settings
from app.services.llm_client import (
    FALLBACK_BETA, LLMClient, LLMError, estimate_cost, image_block, model_for, text_block,
)


class Answer(BaseModel):
    title: str


def fake_response(parsed=Answer(title="ok"), stop_reason="end_turn", model="claude-opus-5-5"):
    return SimpleNamespace(
        parsed_output=parsed, stop_reason=stop_reason, model=model,
        usage=SimpleNamespace(input_tokens=1000, output_tokens=500), _request_id="req_test",
    )


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def fake_client(response=None, error=None):
    messages = FakeMessages(response or fake_response(), error)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def status_error(cls, status):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("error", response=httpx2.Response(status, request=request), body=None)


class TestImageBlock(unittest.TestCase):
    def decode(self, block):
        return Image.open(io.BytesIO(base64.standard_b64decode(block["source"]["data"])))

    def test_large_image_is_resized_to_jpeg(self):
        block = image_block(Image.new("RGB", (4032, 3024), "red"))
        self.assertEqual(block["source"]["media_type"], "image/jpeg")
        self.assertEqual(self.decode(block).size, (1024, 768))

    def test_small_image_keeps_size(self):
        self.assertEqual(self.decode(image_block(Image.new("RGB", (300, 200)))).size, (300, 200))

    def test_exif_rotation_is_applied(self):
        # 픽셀은 가로(400x300)인데 EXIF가 "90도 돌려서 보라"(6)고 하는 휴대폰 사진
        img = Image.new("RGB", (400, 300))
        exif = img.getexif()
        exif[0x0112] = 6
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        rotated = self.decode(image_block(Image.open(io.BytesIO(buffer.getvalue()))))
        self.assertEqual(rotated.size, (300, 400))

    def test_rgba_is_converted(self):
        self.assertEqual(self.decode(image_block(Image.new("RGBA", (10, 10)))).mode, "RGB")


class TestModelAndCost(unittest.TestCase):
    def test_role_falls_back_to_default(self):
        with patch.dict(settings.CLAUDE_MODELS, {"writer": ""}):
            self.assertEqual(model_for("writer"), settings.CLAUDE_MODEL_DEFAULT)

    def test_role_override(self):
        with patch.dict(settings.CLAUDE_MODELS, {"summary": "claude-haiku-5-5"}):
            self.assertEqual(model_for("summary"), "claude-haiku-5-5")

    def test_cost(self):
        self.assertAlmostEqual(estimate_cost("claude-opus-5-5", 1_000_000, 100_000), 4.0 + 2.0)
        self.assertIsNone(estimate_cost("unknown-model", 1, 1))


class TestParse(unittest.IsolatedAsyncioTestCase):
    async def test_success(self):
        client, messages = fake_client()
        result = await LLMClient(client).parse("writer", [text_block("hi")], Answer, system="sys", effort="high")
        self.assertEqual(result.parsed.title, "ok")
        self.assertEqual((result.input_tokens, result.output_tokens), (1000, 500))
        self.assertAlmostEqual(result.cost_usd, (1000 * 4 + 500 * 20) / 1_000_000)
        call = messages.calls[0]
        self.assertIs(call["output_format"], Answer)
        self.assertEqual(call["system"], "sys")
        self.assertEqual(call["output_config"], {"effort": "high"})
        self.assertEqual(call["messages"][0]["content"], [{"type": "text", "text": "hi"}])

    async def test_fallback_on_for_opus_off_for_haiku(self):
        client, messages = fake_client()
        with patch.dict(settings.CLAUDE_MODELS, {"writer": "claude-opus-5-5", "summary": "claude-haiku-5-5"}):
            await LLMClient(client).parse("writer", [], Answer)
            await LLMClient(client).parse("summary", [], Answer)
        self.assertEqual(messages.calls[0]["betas"], [FALLBACK_BETA])
        self.assertEqual(messages.calls[0]["fallbacks"], "default")
        self.assertNotIn("fallbacks", messages.calls[1])

    async def test_no_effort_means_no_output_config(self):
        client, messages = fake_client()
        await LLMClient(client).parse("writer", [], Answer)
        self.assertNotIn("output_config", messages.calls[0])

    async def test_refusal_and_truncation_raise(self):
        for stop_reason, words in [("refusal", "거절"), ("max_tokens", "끊겼")]:
            client, _ = fake_client(fake_response(stop_reason=stop_reason))
            with self.assertRaisesRegex(LLMError, words):
                await LLMClient(client).parse("writer", [], Answer)

    async def test_unparsed_output_raises(self):
        client, _ = fake_client(fake_response(parsed=None))
        with self.assertRaisesRegex(LLMError, "형식"):
            await LLMClient(client).parse("writer", [], Answer)

    async def test_api_errors_become_korean_messages(self):
        cases = [
            (status_error(anthropic.AuthenticationError, 401), "키가 올바르지"),
            (status_error(anthropic.RateLimitError, 429), "너무 많습니다"),
            (status_error(anthropic.InternalServerError, 500), "서버 오류 \\(500\\)"),
        ]
        for error, words in cases:
            client, _ = fake_client(error=error)
            with self.assertRaisesRegex(LLMError, words):
                await LLMClient(client).parse("writer", [], Answer)

    async def test_missing_key_message(self):
        with patch.object(settings, "ANTHROPIC_API_KEY", ""):
            with self.assertRaisesRegex(LLMError, "ANTHROPIC_API_KEY"):
                await LLMClient().parse("writer", [], Answer)


if __name__ == "__main__":
    unittest.main()
