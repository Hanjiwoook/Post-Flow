import time
import os
import pyperclip
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from ...core.config import settings

# 디버그 파일(스크린샷, 편집기 HTML)을 남길 곳: backend/debug_naver_*  (.gitignore의 backend/debug_* 에 해당)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def block_image_indices(block: dict) -> list:
    """사진 블록의 사진 번호 목록 (예전 형식 image_index도 받는다)."""
    indices = block.get("image_indices") or []
    if not indices and block.get("image_index") is not None:
        indices = [block["image_index"]]
    return list(indices)


def unused_image_indices(blocks: list, image_count: int) -> list:
    """
    글의 사진 블록에 없는 사진 번호. 이 사진들은 올리지 않는다.
    AI가 일부러 뺀 사진(영수증의 카드번호, 흔들린 사진 등)이 여기에 들어간다.
    """
    used = {i for b in blocks if b.get("type") == "image" for i in block_image_indices(b)}
    return [i for i in range(image_count) if i not in used]


class NaverBlogAutomationV2:
    def __init__(self):
        self.naver_id = settings.NAVER_ID
        self.naver_pw = settings.NAVER_PW
        self.naver_blog_id = settings.NAVER_BLOG_ID or "ohuks_life"

    def _snap(self, page, name: str, frame=None):
        """어디서 막혔는지 볼 수 있게 화면(과 편집기 HTML)을 남긴다. 실패해도 발행 흐름은 멈추지 않는다."""
        stamp = time.strftime("%H%M%S")
        base = os.path.join(BACKEND_DIR, f"debug_naver_{stamp}_{name}")
        try:
            page.screenshot(path=base + ".png", full_page=True)
            if frame is not None:
                with open(base + ".html", "w", encoding="utf-8") as f:
                    f.write(frame.content())
            print(f"   📷 디버그 저장: {os.path.basename(base)}")
        except Exception as e:
            print(f"   ⚠️ 디버그 저장 실패: {e}")

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
                pyperclip.copy("")  # 비밀번호가 클립보드에 남지 않게 지운다
                # 2026-11 로그인 화면 변경: #log.login → loginBtn_column / loginBtn_row (배치에 따라 하나만 보인다)
                login_btn = page.locator("button[data-nlog-area='login.loginbtn']:visible").first
                if login_btn.count():
                    login_btn.click()
                else:
                    page.keyboard.press("Enter")
                # 로그인 페이지를 벗어날 때까지 기다린다. 보안 확인(캡차)이 나오면 사람이 풀 시간을 준다.
                print("로그인 확인 중... (보안 확인이 나오면 창에서 직접 풀어 주세요, 최대 2분)")
                try:
                    page.wait_for_url(lambda url: "nidlogin" not in url, timeout=120000)
                except Exception:
                    print("❌ 로그인하지 못했습니다 (2분 안에 로그인 페이지를 벗어나지 못함)")
                    self._snap(page, "login_fail")
                    return False

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
                failed_image_indices = []

                for i, block in enumerate(normalized_blocks):
                    b_type = block.get("type", "text")
                    b_value = block.get("value") or ""
                    indices = block_image_indices(block)
                    
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
                            
                            
                            # Focus Fix 및 섹션 간격 추가
                            body_el.click(force=True)
                            page.keyboard.press("Control+End")
                            # 이미지 업로드 후에도 엔터 3번 쳐서 다음 텍스트와 간격 벌리기
                            for _ in range(3):
                                page.keyboard.press("Enter")
                                time.sleep(0.2)
                        except Exception as e:
                            failed_image_indices.extend(indices)
                            print(f"   ⚠️ 사진 {indices} 업로드 실패: {e}")
                            self._snap(page, f"image_fail_{i}", frame)

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

                # 7. 안 쓴 사진은 올리지 않는다 (2026-11-17)
                # 예전에는 블록에 없는 사진을 글 끝에 모두 올렸는데, AI가 일부러 뺀 영수증 사진까지 올라갔다.
                # 빠뜨린 사진은 글쓰기 단계(sanitize_images)가 '뺀 사진'으로 보고하고 앱에서 다시 넣는다.
                skipped = unused_image_indices(normalized_blocks, len(image_paths))
                if skipped:
                    print(f"   🚫 글에 없는 사진 {skipped}은 올리지 않았습니다")
                if failed_image_indices:
                    print(f"   ⚠️ 업로드에 실패한 사진 {failed_image_indices}: 임시저장 글에서 직접 확인해 주세요")

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
                self._snap(page, "before_save", frame)  # 저장 직전 상태 (편집기 구조 확인용)
                page.evaluate("window.scrollTo(0, 0)"); time.sleep(3)
                save_btn = frame.locator("button:has-text('저장'), .save_btn__bzc5B").first
                if save_btn.is_visible():
                    save_btn.click(force=True)
                    print("✅ Mission Accomplished!")
                    time.sleep(5)
                    return True
                print("❌ 저장 버튼을 찾지 못했습니다")
                self._snap(page, "no_save_button", frame)
                return False

            except Exception as e:
                print(f"❌ V2 Error: {e}")
                self._snap(page, "error", locals().get("frame"))
                return False
            finally:
                time.sleep(2); browser.close()

naver_automation_v2 = NaverBlogAutomationV2()
