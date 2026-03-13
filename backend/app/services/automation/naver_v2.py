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

    def publish(self, title: str, blocks: list, image_paths: list[str] = [], images_data: list = [], facts: dict = {}) -> bool:
        print(f"🚀 [V2 인플루언서 중앙 타격 모드] Starting - Title: {title}")
        
        facts = facts if isinstance(facts, dict) else {}
        images_data = images_data if isinstance(images_data, list) else []
        blocks = blocks if isinstance(blocks, list) else []
        
        # 카테고리 맵 개선 (GeminiService와 일치시킴)
        category_map = {
            "외관": ["EXTERIOR"],
            "내부": ["INTERIOR"],
            "메뉴판": ["MENU"],
            "음식": ["FOOD_ITEM"], # GeminiService의 카테고리명과 일치
            "위치": ["MAP"],
            "정보": ["MAP"],
            "영수증": ["RECEIPT"]
        }

        with sync_playwright() as p:
            # ... (생략된 브라우저 로직)
            # ... (중략: 브라우저 실행 및 로그인 로직)
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

                # 6. Assemble Blocks
                used_image_paths = set()

                for i, block in enumerate(blocks):
                    if not block: continue
                    raw_value = block.get("value") or ""
                    if not raw_value and block.get("type") != "divider": continue

                    # [제목]과 [내용] 분리
                    header = ""
                    content = raw_value
                    if "]" in raw_value:
                        parts = raw_value.split("]", 1)
                        header = parts[0].replace("[", "").strip()
                        content = parts[1].strip()

                    print(f"🧩 Processing Section: {header or 'General'}")

                    # --- [STEP 1] 인용구 제목 입력 ---
                    if header and "인사말" not in header:
                        print(f"   🖋️ Adding Quote Title: {header}")
                        frame.locator("button[data-name='quotation']").first.click(force=True)
                        time.sleep(2)
                        page.keyboard.type(header, delay=50)
                        
                        print("   🔓 Exiting Quote block...")
                        page.keyboard.press("ArrowDown") # 출처칸
                        time.sleep(0.5)
                        page.keyboard.press("ArrowDown") # 본문 탈출
                        time.sleep(1)
                        page.keyboard.press("Enter") 

                    # --- [STEP 2] 사진 업로드 및 정밀 매칭 ---
                    target_categories = []
                    specific_menu = None
                    
                    # 섹션 제목에서 특정 메뉴 추출 (예: [음식:라멘] -> 라멘)
                    if ":" in header:
                        parts = header.split(":", 1)
                        header_key = parts[0].strip()
                        specific_menu = parts[1].strip()
                    else:
                        header_key = header

                    for keyword, cats in category_map.items():
                        if keyword in header_key:
                            for c in cats:
                                if c not in target_categories:
                                    target_categories.append(c)
                    
                    if target_categories and images_data:
                        # 카테고리 매칭 로직 개선: 특정 메뉴가 지정된 경우(FOOD_ITEM:라멘) 우선순위 매칭
                        def is_match(img_cat, targets, menu_name=None):
                            if not img_cat: return False
                            img_cat = img_cat.upper()
                            
                            # 1. 특정 메뉴 이름이 헤더에 있을 경우 (예: [음식:라멘])
                            if menu_name and "FOOD_ITEM" in targets:
                                if img_cat == f"FOOD_ITEM:{menu_name.upper()}":
                                    return True
                            
                            # 2. 일반 카테고리 매칭
                            for t in targets:
                                if img_cat == t or img_cat.startswith(f"{t}:"):
                                    # 만약 헤더에 특정 메뉴가 없으면 일반 FOOD_ITEM은 다 가져옴
                                    if t == "FOOD_ITEM" and menu_name:
                                        continue # 특정 메뉴 헤더일 때는 일반 항목 제외
                                    return True
                            return False

                        section_images = [
                            img.get("path") for img in images_data 
                            if img and is_match(img.get("category"), target_categories, specific_menu) 
                            and img.get("path") not in used_image_paths
                        ]
                        if section_images:
                            num_imgs = len(section_images)
                            print(f"   📸 Uploading {num_imgs} images for {target_categories}...")
                            try:
                                with page.expect_file_chooser(timeout=60000) as fc_info:
                                    frame.locator("button[data-name='image']").first.click(force=True)
                                fc_info.value.set_files(section_images)
                                
                                # 여러 장일 때 사용자 아이디어: 화면 중앙 강제 클릭
                                if num_imgs > 1:
                                    print("   🎯 Multiple images detected. Aiming for the center of the popup...")
                                    time.sleep(5) # 팝업이 뜰 때까지 대기
                                    
                                    viewport = page.viewport_size
                                    center_x = viewport['width'] / 2
                                    center_y = viewport['height'] / 2
                                    
                                    print(f"   🖱️ Clicking center coordinates ({center_x}, {center_y})")
                                    page.mouse.click(center_x, center_y)
                                    time.sleep(2)
                                    page.mouse.click(center_x, center_y + 50)
                                    print("   ✅ Center clicks performed.")

                                # 장당 10초 정밀 대기
                                wait_time = num_imgs * 10
                                print(f"   ⏳ Precision Wait: {wait_time}s")
                                time.sleep(wait_time)
                                
                                try:
                                    frame.wait_for_selector(".se-progress-bar", state="hidden", timeout=10000)
                                except: pass
                                
                                for path in section_images: used_image_paths.add(path)
                                
                                # [Focus Fix] 에디터 하단으로 확실하게 이동
                                print("   ⚓ Recovering focus to the bottom...")
                                body_el.click(force=True)
                                time.sleep(1)
                                page.keyboard.press("Control+End")
                                time.sleep(1)
                                page.keyboard.press("Enter")
                                
                            except Exception as e:
                                print(f"   ⚠️ Upload Error: {e}")

                    # --- [STEP 3] 본문 내용 입력 ---
                    if content:
                        print(f"   📝 Typing Content...")
                        page.keyboard.type(content, delay=30)
                        page.keyboard.press("Enter")
                        time.sleep(2)
                    
                    if block.get("type") == "divider":
                        frame.locator("button[data-name='horizontal-line']").first.click(force=True)
                        time.sleep(2)

                # --- [STEP 4] Safety Net: 누락된 이미지 처리 ---
                remaining_images = [path for path in image_paths if path not in used_image_paths]
                if remaining_images:
                    print(f"   🛡️ Safety Net: Uploading {len(remaining_images)} remaining images...")
                    try:
                        body_el.click(force=True)
                        page.keyboard.press("Control+End")
                        page.keyboard.press("Enter")
                        
                        with page.expect_file_chooser(timeout=60000) as fc_info:
                            frame.locator("button[data-name='image']").first.click(force=True)
                        fc_info.value.set_files(remaining_images)
                        
                        if len(remaining_images) > 1:
                            time.sleep(5)
                            viewport = page.viewport_size
                            page.mouse.click(viewport['width']/2, viewport['height']/2)
                            time.sleep(1)
                            page.mouse.click(viewport['width']/2, viewport['height']/2 + 50)

                        time.sleep(len(remaining_images) * 10)
                        print("   ✅ Remaining images uploaded.")
                    except Exception as e:
                        print(f"   ⚠️ Safety Net Error: {e}")

                # 7. Final Touch
                print("🌟 Finalizing: Select All & Center Align")
                body_el.click(force=True); time.sleep(1)
                page.keyboard.press("Control+a"); time.sleep(1.5)
                align_btn = frame.locator("button[data-name='align-center']").first
                if not align_btn.is_visible():
                    more_btn = frame.locator("button[data-name='more']").first
                    if more_btn.is_visible(): more_btn.click(force=True); time.sleep(1)
                if align_btn.is_visible(): align_btn.click(force=True)
                time.sleep(2); page.keyboard.press("ArrowDown") 

                # 8. Save
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
