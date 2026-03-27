import time
import os
import pyperclip
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from ...core.config import settings

class NaverBlogAutomationV2:
    def __init__(self):
        self.naver_id = settings.NAVER_ID
        self.naver_pw = settings.NAVER_PW
        self.naver_blog_id = settings.NAVER_BLOG_ID or "ohuks_life"

    def safe_hide_overlays(self, frame):
        """도움말 및 마스크 강제 제거"""
        try:
            frame.evaluate("""() => {
                const selectors = [
                    '.se-help-panel', '.se-help-container', '.se-tutorial-container', 
                    '.se-popup-container', '.se-popup-alert', '.se-l-mask'
                ];
                selectors.forEach(s => {
                    document.querySelectorAll(s).forEach(el => {
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                    });
                });
            }""")
        except: pass

    def publish(self, title: str, blocks: list, image_paths: list[str] = [], images_data: list = [], facts: dict = {}, max_retries: int = 3) -> bool:
        for attempt in range(max_retries):
            print(f"🔄 [V2 봇 안정화] 네이버 자동 발행 시작 (시도 {attempt + 1}/{max_retries})")
            success = self._execute_publish(title, blocks, image_paths, images_data, facts)
            if success:
                return True
            if attempt < max_retries - 1:
                print(f"⚠️ [V2 봇] 예외 발생. 트래픽 안정화를 위해 10초 대기 후 재시도합니다...")
                time.sleep(10)
        print("❌ [V2 봇] 모든 재시도가 실패했습니다. 포스팅을 중단합니다.")
        return False

    def _execute_publish(self, title: str, blocks: list, image_paths: list[str] = [], images_data: list = [], facts: dict = {}) -> bool:
        print(f"🚀 [V2 인플루언서 콜라주 모드] Starting - Title: {title}")
        
        # 데이터 정규화
        normalized_blocks = []
        for b in blocks:
            if hasattr(b, "model_dump"): normalized_blocks.append(b.model_dump())
            elif isinstance(b, dict): normalized_blocks.append(b)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) 
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            Stealth().apply_stealth_sync(page)

            try:
                # 1. Login
                page.goto("https://nid.naver.com/nidlogin.login")
                page.click("#id"); pyperclip.copy(self.naver_id); page.keyboard.press("Control+v")
                page.click("#pw"); pyperclip.copy(self.naver_pw); page.keyboard.press("Control+v")
                page.click("#log\.login")
                time.sleep(3)

                # 2. Access Editor
                page.goto(f"https://blog.naver.com/{self.naver_blog_id}?Redirect=Write&")
                page.wait_for_selector("iframe#mainFrame", timeout=30000)
                frame = next(f for f in page.frames if "mainFrame" in f.name)

                # 3. Stabilize
                print("Waiting for editor to stabilize...")
                time.sleep(15)
                try:
                    cancel_btn = frame.locator(".se-popup-button-cancel").first
                    if cancel_btn.is_visible(timeout=3000): cancel_btn.click(force=True); time.sleep(5)
                except: pass
                self.safe_hide_overlays(frame)

                # 4. Title
                print("Typing Title...")
                title_el = frame.locator(".se-documentTitle").first
                title_el.click(force=True); time.sleep(1)
                page.keyboard.type(title, delay=50); time.sleep(1)

                # 5. Body Focus
                body_el = frame.locator(".se-content").first
                body_el.click(force=True); time.sleep(1)

                # 6. Process Blocks
                used_image_indices = set()

                for i, block in enumerate(normalized_blocks):
                    b_type = block.get("type", "text")
                    b_value = block.get("value") or ""
                    # 다중 이미지 인덱스 지원
                    indices = block.get("image_indices", [])
                    if not indices and block.get("image_index") is not None:
                        indices = [block["image_index"]]
                    
                    print(f"🧩 [{i+1}/{len(normalized_blocks)}] Block: {b_type}")

                    if b_type == "text" and b_value:
                        page.keyboard.type(b_value, delay=30)
                        page.keyboard.press("Enter")
                        # 각 항목(인사말, 외관 등) 종료 후 간격 벌리기
                        for _ in range(3): 
                            page.keyboard.press("Enter")
                            time.sleep(0.2)
                        time.sleep(1.5)

                    elif b_type == "image" and indices:
                        paths = [image_paths[idx] for idx in indices if 0 <= idx < len(image_paths)]
                        if not paths: continue
                        
                        print(f"   📸 Uploading {len(paths)} images (Collage Mode)")
                        try:
                            with page.expect_file_chooser(timeout=60000) as fc_info:
                                frame.locator("button[data-name='image']").first.click(force=True)
                            fc_info.value.set_files(paths)
                            
                            # 콜라주 팝업 처리 (여러 장일 때)
                            if len(paths) > 1:
                                print("   🎯 Multiple images: Selecting 'Collage' layout...")
                                time.sleep(5)
                                viewport = page.viewport_size
                                # 네이버 팝업 위치 보정 (중앙 클릭)
                                page.mouse.click(viewport['width']/2, viewport['height']/2)
                                time.sleep(1)
                                page.mouse.click(viewport['width']/2, viewport['height']/2 + 50)

                            # [유저 요청] 사진 업로드 안정성을 위해 넉넉한 대기 시간 부여 (기본 10초 + 장당 추가)
                            print(f"   ⏳ Waiting for upload to complete (10s + alpha)...")
                            time.sleep(10 + (len(paths) * 2)) 
                            
                            for idx in indices: used_image_indices.add(idx)
                            
                            # Focus Fix 및 섹션 간격 추가
                            body_el.click(force=True)
                            page.keyboard.press("Control+End")
                            # 이미지 업로드 후에도 엔터 3번 쳐서 다음 텍스트와 간격 벌리기
                            for _ in range(3):
                                page.keyboard.press("Enter")
                                time.sleep(0.2)
                        except Exception as e:
                            print(f"   ⚠️ Image Error: {e}")

                    elif b_type == "quote" and b_value:
                        frame.locator("button[data-name='quotation']").first.click(force=True)
                        time.sleep(2)
                        page.keyboard.type(b_value, delay=30)
                        page.keyboard.press("ArrowDown")
                        time.sleep(0.5)
                        page.keyboard.press("ArrowDown")
                        time.sleep(1)
                        page.keyboard.press("Enter")
                        # 인용구 뒤에도 간격 추가
                        for _ in range(3):
                            page.keyboard.press("Enter")
                            time.sleep(0.2)

                    elif b_type == "divider":
                        frame.locator("button[data-name='horizontal-line']").first.click(force=True)
                        time.sleep(2)
                        page.keyboard.press("ArrowDown")
                        page.keyboard.press("Enter")

                # 7. Safety Net: 누락 사진 처리
                remaining = [image_paths[idx] for idx in range(len(image_paths)) if idx not in used_image_indices]
                if remaining:
                    print(f"   🛡️ Safety Net: {len(remaining)} images")
                    page.keyboard.press("Control+End"); page.keyboard.press("Enter")
                    with page.expect_file_chooser(timeout=60000) as fc_info:
                        frame.locator("button[data-name='image']").first.click(force=True)
                    fc_info.value.set_files(remaining)
                    time.sleep(len(remaining) * 8)

                # 8. Align Center
                body_el.click(force=True); time.sleep(1)
                page.keyboard.press("Control+a"); time.sleep(1.5)
                align_btn = frame.locator("button[data-name='align-center']").first
                if not align_btn.is_visible():
                    more_btn = frame.locator("button[data-name='more']").first
                    if more_btn.is_visible(): more_btn.click(force=True); time.sleep(1)
                if align_btn.is_visible(): align_btn.click(force=True)
                time.sleep(2); page.keyboard.press("ArrowDown") 

                # 9. Save
                page.evaluate("window.scrollTo(0, 0)"); time.sleep(3)
                save_btn = frame.locator("button:has-text('저장'), .save_btn__bzc5B").first
                if save_btn.is_visible():
                    save_btn.click(force=True)
                    print("✅ Mission Accomplished!")
                    time.sleep(5)
                    return True
                return False

            except Exception as e:
                print(f"❌ V2 Error: {e}"); return False
            finally:
                time.sleep(2); browser.close()

naver_automation_v2 = NaverBlogAutomationV2()
