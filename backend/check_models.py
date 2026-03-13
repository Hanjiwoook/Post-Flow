import google.generativeai as genai
import os
from dotenv import load_dotenv

# .env 파일 로드
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ GEMINI_API_KEY가 .env 파일에 설정되어 있지 않습니다.")
else:
    print(f"🔑 API Key: {api_key[:10]}********")
    genai.configure(api_key=api_key)

    print("\n🔍 사용 가능한 Gemini 모델 리스트를 확인 중입니다...\n")
    try:
        model_list = genai.list_models()
        count = 0
        for m in model_list:
            if 'generateContent' in m.supported_generation_methods:
                print(f"✅ 모델명: {m.name}")
                print(f"   - 설명: {m.description}")
                print(f"   - 지원 버전: {m.supported_generation_methods}")
                print("-" * 50)
                count += 1
        
        if count == 0:
            print("⚠️ 'generateContent'를 지원하는 모델을 찾지 못했습니다.")
        else:
            print(f"\n✨ 총 {count}개의 생성 모델을 찾았습니다!")
            
    except Exception as e:
        print(f"❌ 모델 리스트 확인 중 오류 발생: {e}")
