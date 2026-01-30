import os
import io
import json
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

# 1. 환경 설정
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# 모델 설정 (지욱님의 2.5 Flash!)
model = genai.GenerativeModel('gemini-2.5-flash')

app = FastAPI(title="Post Flow API")

@app.get("/")
def read_root():
    return {"message": "Post Flow Server is Running!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

# 2. [업그레이드] 다중 이미지 분석 API
@app.post("/api/v1/analyze")
async def analyze_images(
    files: List[UploadFile] = File(...),  # 이제 리스트로 받습니다! (여러 장 가능)
    style: str = Form("emotional")
):
    # [QA 검증] 이미지 개수 제한 (SRS FR-C01 준수)
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="이미지는 최대 10장까지만 가능합니다.")

    try:
        image_parts = []
        
        # (1) 업로드된 모든 이미지를 AI가 읽을 수 있게 변환
        for file in files:
            content = await file.read()
            image = Image.open(io.BytesIO(content))
            image_parts.append(image)

        # (2) 프롬프트: JSON 형식으로 달라고 강력하게 요구
        prompt = f"""
        너는 네이버 블로그 '파워 블로거'야. 
        이 {len(files)}장의 사진들을 보고 하나의 완벽한 블로그 포스팅을 작성해줘.
        
        [필수 요구사항]
        1. 말투: {style} (친근하고, 이모지 많이 사용)
        2. 사진들에 대한 묘사를 자연스럽게 연결할 것.
        3. 반드시 아래 JSON 형식으로만 출력해줘. (마크다운 코드블럭 없이 순수 JSON만)
        
        {{
            "title": "여기에 낚시성 있는 매력적인 제목",
            "content": "여기에 본문 내용 (줄바꿈은 \\n 사용)",
            "tags": ["#태그1", "#태그2", "#태그3", "#태그4", "#태그5"]
        }}
        """

        # (3) AI에게 [프롬프트 + 사진뭉치] 전송
        response = model.generate_content([prompt, *image_parts])
        
        # (4) 결과 반환 (JSON 문자열을 파이썬 객체로 변환 시도)
        try:
            cleaned_text = response.text.replace("```json", "").replace("```", "").strip()
            result_json = json.loads(cleaned_text)
        except:
            # AI가 가끔 JSON 형식을 어길 때를 대비한 예외처리
            result_json = {
                "title": "제목 생성 실패",
                "content": response.text,
                "tags": []
            }
            
        return {
            "success": True,
            "image_count": len(files),
            "result": result_json
        }

    except Exception as e:
        return {"success": False, "error": str(e)}