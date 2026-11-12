"""스타일 미리보기 테스트"""
import httpx
import asyncio
import json

async def main():
    async with httpx.AsyncClient(timeout=60) as client:
        # 스타일 미리보기
        print("=== POST /api/v1/style/preview ===")
        resp = await client.post(
            "http://localhost:8000/api/v1/style/preview",
            json={
                "sample_text": "오늘 남자친구랑 홍대에 새로 생긴 라멘집에 갔다. 라멘이 맛있었다."
            }
        )
        print(f"Status: {resp.status_code}")
        data = resp.json()
        
        if data.get("success"):
            print(f"\n원본: {data['data']['original']}")
            print(f"\n적용된 프로필: {data['data']['profile_name']}")
            print(f"\n변환 결과:\n{data['data']['styled']}")
        else:
            print(f"Error: {data.get('message')}")

if __name__ == "__main__":
    asyncio.run(main())
