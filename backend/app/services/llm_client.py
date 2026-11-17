"""
Claude API 공통 호출 모듈.

서비스 코드(글쓰기, 요약, 스타일 학습 등)는 이 모듈의 `llm.parse()`만 부른다.
  - 결과를 Pydantic 모델로 받는다 (구조화된 출력, `output_format`)
  - 사진(PIL)을 API용 이미지 블록으로 바꾼다 (회전 보정, 크기 축소, JPEG)
  - 거절(refusal), 길이 초과(max_tokens) 같은 실패를 한국어 메시지의 LLMError로 바꾼다
  - 호출마다 토큰 사용량과 추정 비용을 기록한다

비동기 클라이언트(AsyncAnthropic)를 써서, AI가 글을 쓰는 동안에도 서버가 다른 요청을 받을 수 있다.
"""
import base64
import io
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type, TypeVar

import anthropic
from PIL import Image, ImageOps
from pydantic import BaseModel

from ..core.config import settings

T = TypeVar("T", bound=BaseModel)

# 사진 긴 변 최대 길이. 1024px면 사진 1장에 약 1,000~1,400토큰이다.
IMAGE_MAX_SIDE = 1024
IMAGE_JPEG_QUALITY = 85

DEFAULT_MAX_TOKENS = 16000

# 거절되면 같은 요청을 다른 모델로 다시 돌리는 서버 기능 (Haiku에는 없다)
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# 추정 비용 계산용 가격 (USD / 100만 토큰, 2026-11 기준 공식 가격). 실제 청구액은 Console에서 확인한다.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


class LLMError(Exception):
    """AI 호출 실패. message는 사용자에게 보여 줄 수 있는 한국어 문장이다."""


@dataclass
class LLMResult:
    parsed: Any
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Optional[float]
    request_id: Optional[str] = None


def model_for(role: str) -> str:
    """용도(role)에 맞는 모델 이름. .env에 따로 정하지 않았으면 기본 모델."""
    return settings.CLAUDE_MODELS.get(role) or settings.CLAUDE_MODEL_DEFAULT


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    price = PRICES.get(model)
    if price is None:
        return None
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000


def image_block(img: Image.Image, max_side: int = IMAGE_MAX_SIDE) -> Dict:
    """PIL 사진을 API 이미지 블록으로 바꾼다."""
    # 휴대폰 사진은 EXIF 회전 정보만 있고 픽셀은 누워 있을 수 있어서, 먼저 보이는 방향으로 돌린다
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if max(img.size) > max_side:
        ratio = max_side / max(img.size)
        img = img.resize((round(img.size[0] * ratio), round(img.size[1] * ratio)), Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=IMAGE_JPEG_QUALITY)
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.standard_b64encode(buffer.getvalue()).decode("ascii"),
        },
    }


def text_block(text: str) -> Dict:
    return {"type": "text", "text": text}


class LLMClient:
    def __init__(self, client: Any = None):
        # 테스트에서는 가짜 클라이언트를 넣는다. 실제 클라이언트는 처음 쓸 때 만든다.
        self._client = client

    def _get_client(self):
        if self._client is None:
            if not settings.ANTHROPIC_API_KEY:
                raise LLMError("Claude API 키가 설정되지 않았습니다. backend/.env에 ANTHROPIC_API_KEY를 추가해 주세요.")
            self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    async def parse(
        self,
        role: str,
        content: List[Dict],
        output_format: Type[T],
        system: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        effort: Optional[str] = None,
    ) -> LLMResult:
        """
        Claude를 호출해 결과를 output_format(Pydantic 모델)으로 받는다.

        role: 용도 ("writer", "reviewer", "summary", "style", "refine") → 모델 선택
        content: 사용자 메시지 블록 목록 (text_block, image_block)
        effort: "low" | "medium" | "high" ... 생략하면 모델 기본값
        """
        model = model_for(role)
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": content}],
            "output_format": output_format,
        }
        if system:
            kwargs["system"] = system
        if effort:
            kwargs["output_config"] = {"effort": effort}
        if not model.startswith("claude-haiku"):
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"

        client = self._get_client()
        try:
            response = await client.beta.messages.parse(**kwargs)
        except anthropic.AuthenticationError:
            raise LLMError("Claude API 키가 올바르지 않습니다. backend/.env의 ANTHROPIC_API_KEY를 확인해 주세요.")
        except anthropic.PermissionDeniedError:
            raise LLMError("이 API 키로는 요청한 모델을 쓸 수 없습니다.")
        except anthropic.NotFoundError:
            raise LLMError(f"모델 이름을 찾을 수 없습니다: {model}")
        except anthropic.RateLimitError:
            raise LLMError("요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")
        except anthropic.BadRequestError as e:
            # 크레딧 부족도 400으로 온다
            raise LLMError(f"Claude API 요청 오류: {e.message}")
        except anthropic.APIStatusError as e:
            raise LLMError(f"Claude API 서버 오류 ({e.status_code}). 잠시 후 다시 시도해 주세요.")
        except anthropic.APIConnectionError:
            raise LLMError("Claude API에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.")

        request_id = getattr(response, "_request_id", None)

        # 실패한 응답도 비용이 청구되므로, 검사보다 먼저 사용량을 기록한다
        # 거절되어 다른 모델이 대신 답했으면 그 모델 이름이 온다
        used_model = response.model or model
        usage = response.usage
        cost = estimate_cost(used_model, usage.input_tokens, usage.output_tokens)
        cost_text = f"${cost:.4f}" if cost is not None else "가격 정보 없음"
        print(f"  💰 [{role}] {used_model}: 입력 {usage.input_tokens:,} / 출력 {usage.output_tokens:,} 토큰, "
              f"추정 {cost_text} (stop_reason={response.stop_reason}, request_id={request_id})")

        if response.stop_reason == "refusal":
            raise LLMError("AI가 이 요청에 대한 응답을 거절했습니다.")
        if response.stop_reason == "max_tokens":
            raise LLMError("AI 응답이 너무 길어 중간에 끊겼습니다.")
        if response.parsed_output is None:
            raise LLMError("AI 응답을 정해진 형식으로 읽지 못했습니다.")

        return LLMResult(
            parsed=response.parsed_output,
            model=used_model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=cost,
            request_id=request_id,
        )


llm = LLMClient()
