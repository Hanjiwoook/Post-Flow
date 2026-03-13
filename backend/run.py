import asyncio
import sys
import uvicorn

if __name__ == "__main__":
    # Windows에서 Playwright 비동기 사용을 위한 필수 설정
    if sys.platform == 'win32':
        print("🔧 [System] Forcing ProactorEventLoopPolicy for Windows...")
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # uvicorn 실행 (app.main:app 로딩 전에 정책이 설정됨)
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        loop="asyncio"
    )
