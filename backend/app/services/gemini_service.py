import google.generativeai as genai
from PIL import Image
import json
import io
from typing import List
from ..core.config import settings
from ..schemas.post import AnalyzeResult

class GeminiService:
    def __init__(self):
        # Gemini 설정 초기화
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in .env")
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.GEMINI_MODEL_NAME)

    async def analyze_images(self, images: List[Image.Image], style: str) -> AnalyzeResult:
        """
        이미지 리스트를 받아 블로그 포스팅 초안(JSON)을 생성함
        """
        prompt = f"""
        너는 네이버 블로그 '파워 블로거'야. 
        이 {len(images)}장의 사진들을 보고 하나의 완벽한 블로그 포스팅을 작성해줘.
        
        [필수 요구사항]
        1. 말투: {style} (친근하고, 이모지 많이 사용)
        2. 사진들에 대한 묘사를 자연스럽게 연결할 것.
        3. 반드시 아래 JSON 형식으로만 출력해줘. (마크다운 코드블럭 없이 순수 JSON만)
        
        {{
            "title": "여기에 낚시성 있는 매력적인 제목",
            "content": "여기에 본문 내용 (줄바꿈은 \n 사용)",
            "tags": ["#태그1", "#태그2", "#태그3", "#태그4", "#태그5"]
        }}
        """

        try:
            # AI 요청
            response = self.model.generate_content([prompt, *images])
            
            # 응답 파싱 (JSON 추출)
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            
            try:
                result_dict = json.loads(cleaned_text)
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 fallback
                # (실제 운영 시에는 Retry 로직이나 정규표현식 파싱 도입 권장)
                return AnalyzeResult(
                    title="제목 생성 실패 (AI 응답 오류)",
                    content=response.text,
                    tags=["#오류", "#AI"]
                )

            return AnalyzeResult(
                title=result_dict.get("title", ""),
                content=result_dict.get("content", ""),
                tags=result_dict.get("tags", [])
            )

        except Exception as e:
            # 로그 남기기 (print 대신 logging 사용 권장)
            print(f"Gemini Error: {e}")
            raise e

gemini_service = GeminiService()
