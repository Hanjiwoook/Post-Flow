import google.generativeai as genai
import os
from dotenv import load_dotenv

# 1. 환경변수 로드
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ API 키가 없습니다. .env 파일을 확인하세요.")
else:
    # 2. 구글 서버에 접속
    genai.configure(api_key=api_key)
    
    print(f"🔑 확인된 API 키: {api_key[:5]}...")
    print("\n📋 [내 계정에서 사용 가능한 모델 목록]")
    print("-" * 40)
    
    try:
        # 3. 사용 가능한 모든 모델을 조회해서 출력
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"✅ 발견됨: {m.name}")
                available_models.append(m.name)
        
        if not available_models:
            print("⚠️ 사용 가능한 모델이 하나도 없습니다. API 키 설정을 확인해야 합니다.")
            
    except Exception as e:
        print(f"❌ 에러 발생: {e}")