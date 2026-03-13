import time
import os
import pyperclip
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from ...core.config import settings

class NaverBlogAutomation:
    def __init__(self):
        self.naver_id = settings.NAVER_ID
        self.naver_pw = settings.NAVER_PW
        self.naver_blog_id = settings.NAVER_BLOG_ID or "ohuks_life"

    def safe_hide_overlays(self, frame):
        """Hide help layers and masks safely"""
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
                        el.style.zIndex = '-1';
                    });
                });
            }""")
        except: pass

    def publish(self, title: str, blocks: list, image_paths: list[str] = [], images_data: list = [], facts: dict = {}) -> bool:
        print(f"🚀 [HUMAN MODE] Starting - Title: {title}")
        
        category_map = {
            "외관": "EXTERIOR",
            "내부": "INTERIOR",
            "메뉴판": "MENU",
            "음식": "FOOD_MAIN",
            "위치": "MAP",
            "정보": "MAP"
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) 
            page = browser.new_page(viewport={'width': 1280, 'height': 800})
            Stealth().apply_stealth_sync(page)

            try:
                # 1. Login
                page.goto("https://nid.naver.com/nidlogin.login")
                page.click("#id"); pyperclip.copy(self.naver_id); page.keyboard.press("Control+v")
                page.click("#pw"); pyperclip.copy(self.naver_pw); page.keyboard.press("Control+v")
                page.click("#log\\.login")
                time.sleep(3)

                # 2. Access Editor
                page.goto(f"https://blog.naver.com/{self.naver_blog_id}?Redirect=Write&")
                page.wait_for_selector("iframe#mainFrame", timeout=30000)
                frame = next(f for f in page.frames if "mainFrame" in f.name)

                # 3. Wait for full load & Aggressive Popup Clear
                print("Waiting for editor to settle...")
                time.sleep(12) # 충분히 기다림
                self.safe_hide_overlays(frame)
                
                # 팝업 닫기 (취소 버튼 클릭)
                try:
                    cancel_btn = frame.locator(".se-popup-button-cancel").first
                    if cancel_btn.is_visible(timeout=3000):
                        cancel_btn.click(force=True)
                        print("Closed 'Draft Load' popup.")
                        time.sleep(2) # 팝업 닫힌 후 마스크 사라질 시간 대기
                        self.safe_hide_overlays(frame) # 다시 한번 마스크 제거
                except: pass

                # 4. Title: Coordinate Click (Proven reliable)
                print("Typing Title...")
                title_el = frame.locator(".se-documentTitle").first
                box = title_el.bounding_box()
                if box:
                    # 마우스로 좌표를 직접 클릭 (가장 확실함)
                    page.mouse.click(box['x'] + 50, box['y'] + 20)
                    time.sleep(1)
                    page.mouse.click(box['x'] + 50, box['y'] + 20) # 확실히 한 번 더 클릭
                    time.sleep(1)
                    page.keyboard.insert_text(title)
                    time.sleep(1)
                else:
                    print("❌ Title area not found")

                # 5. Body: Coordinate Click
                print("Focusing Body...")
                body_el = frame.locator(".se-content").first
                box = body_el.bounding_box()
                if box:
                    page.mouse.click(box['x'] + 50, box['y'] + 50)
                    time.sleep(1.5)
                else:
                    print("❌ Body area not found")

                # 6. Assemble Blocks
                used_image_paths = set()

                for i, block in enumerate(blocks):
                    b_type = block.get("type")
                    b_value = block.get("value", "")
                    if not b_value and b_type != "divider": continue
                        
                    print(f"🧩 Processing {b_type} block...")

                    if b_type == "text" or b_type == "quote":
                        if b_type == "quote":
                            quote_btn = frame.locator("button[data-name='quotation']").first
                            if quote_btn.is_visible():
                                quote_btn.click(force=True)
                                time.sleep(2)
                        
                        # 텍스트 입력
                        page.keyboard.insert_text(b_value)
                        page.keyboard.press("Enter")
                        
                        if b_type == "quote":
                            page.keyboard.press("ArrowDown")
                            page.keyboard.press("Enter")
                        
                        time.sleep(1)
                        
                        # 사진 업로드
                        target_category = None
                        for keyword, cat in category_map.items():
                            if keyword in b_value:
                                target_category = cat
                                break
                        
                        if target_category and images_data:
                            section_images = [img.get("path") for img in images_data if img.get("category") == target_category and img.get("path") not in used_image_paths]
                            
                            if section_images:
                                print(f"📸 Uploading {len(section_images)} images for {target_category}...")
                                try:
                                    with page.expect_file_chooser() as fc_info:
                                        frame.locator("button[data-name='image']").first.click(force=True)
                                    file_chooser = fc_info.value
                                    file_chooser.set_files(section_images)
                                    time.sleep(5)
                                    
                                    for path in section_images:
                                        used_image_paths.add(path)
                                    
                                    # 사진 업로드 후 다시 본문 클릭해서 포커스 유지
                                    page.mouse.click(box['x'] + 50, box['y'] + 50) # Body 좌표 다시 클릭
                                    page.keyboard.press("End")
                                    page.keyboard.press("Enter")
                                except: pass
                    
                    elif b_type == "divider":
                        divider_btn = frame.locator("button[data-name='horizontal-line']").first
                        if divider_btn.is_visible():
                            divider_btn.click(force=True)
                            time.sleep(1)

                # 7. 나머지 사진 처리
                remaining_images = [path for path in image_paths if path not in used_image_paths]
                if remaining_images:
                    print(f"📸 Uploading {len(remaining_images)} remaining images...")
                    try:
                        with page.expect_file_chooser() as fc_info:
                            frame.locator("button[data-name='image']").first.click(force=True)
                        file_chooser = fc_info.value
                        file_chooser.set_files(remaining_images)
                        time.sleep(5)
                    except: pass

                # 8. Save
                print("Finalizing...")
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(2)
                save_btn = frame.locator("button:has-text('저장'), .save_btn__bzc5B").first
                if save_btn.is_visible():
                    save_btn.click(force=True)
                    print("✅ Mission Accomplished!")
                    time.sleep(5)
                    return True
                
                return False

            except Exception as e:
                print(f"❌ Error: {e}")
                return False
            finally:
                time.sleep(2)
                browser.close()

naver_automation = NaverBlogAutomation()
