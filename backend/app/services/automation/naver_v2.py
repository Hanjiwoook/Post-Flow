import time
import os
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from ...core.config import settings
from .naver_session import SAVE_LOGIN_COMMAND, first_page, has_saved_login, is_login_page, open_browser
from .editor_check import check_editor_html

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


QUOTE_STYLES = {"default", "quotation_line", "quotation_bubble", "quotation_underline",
                "quotation_postit", "quotation_corner"}
QUOTE_FONT_SIZE = "fs15"   # 여자친구 글의 글씨 크기 (본문 기본도 15, 인용구 기본은 더 크다)


def pick_place_result(result_texts: list, address: str) -> int:
    """
    장소 검색 결과 중 주소가 가장 잘 맞는 항목 번호. 같은 이름의 지점이 여러 개일 수 있다.
    주소의 도로명·동 같은 단어가 결과 글자에 몇 개 들어 있는지로 고르고, 단서가 없으면 첫 번째.
    """
    if not result_texts:
        return -1
    words = [w for w in (address or "").split() if len(w) >= 2 and not w.endswith(("시", "도"))]
    scores = [sum(w in text for w in words) for text in result_texts]
    best = max(range(len(scores)), key=lambda i: scores[i])
    return best if scores[best] > 0 else 0


class NaverBlogAutomationV2:
    def __init__(self):
        self.naver_blog_id = settings.NAVER_BLOG_ID or "ohuks_life"
        # 마지막 실행의 저장 전 자가 검사 결과 (빈 목록 = 고칠 것 없음). 문제가 있어도 임시저장은 한다:
        # 비공개 임시저장이라 손해가 없고, 다시 돌리면 사진 업로드부터 몇 분이 든다 (11/18 결정).
        self.last_problems: list = []
        # 마지막 실행이 로그인이 없거나 만료돼서 멈췄는지. 이때는 다시 시도해도 똑같이 실패하고,
        # 로그인 페이지를 여러 번 여는 것이 네이버 보호조치 위험만 키우므로 재시도하지 않는다 (11/19).
        self.login_required: bool = False
        # 앱에 보여줄 마지막 실패 이유 (성공하면 빈 문자열)와 지금 단계를 알려 줄 함수 (6-4, 11/19).
        # on_step은 발행 작업(posts.py)이 DB에 단계를 적으려고 넣는다. 없으면 아무것도 하지 않는다.
        self.last_error: str = ""
        self.on_step = None

    def _step(self, text: str):
        """지금 단계를 알린다. 알리다 실패해도 발행은 멈추지 않는다."""
        if self.on_step:
            try:
                self.on_step(text)
            except Exception as e:
                print(f"⚠️ 단계 기록 실패: {e}")

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

    def _insert_quote(self, page, frame, text: str, style: str) -> bool:
        """인용구 스타일을 골라 넣고 글을 쓴다 (글씨 크기 15는 마지막 정렬 단계에서 한 번에). 실패하면 False."""
        style = style if style in QUOTE_STYLES else "default"
        try:
            frame.locator("button[data-name='quotation'].se-document-toolbar-select-option-button").first.click()
            time.sleep(1)
            frame.locator(f"button[data-name='quotation'][data-value='{style}']").first.click()
            time.sleep(1.5)
            page.keyboard.type(text, delay=30)
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"   ⚠️ 인용구({style}) 넣기 실패: {e}")
            self._snap(page, "quote_fail", frame)
            return False

    def _align_all_center(self, page, frame, body_el) -> bool:
        """
        전체 선택 → 글씨 크기 15 → 정렬 드롭다운 → 가운데. 끝나고 왼쪽 정렬 문단 수를 세서 알린다.
        여자친구 글은 본문·인용구 모두 15라서 마지막에 한 번에 맞춘다. 인용구마다 선택하면 꺾인 줄 때문에
        첫 줄이 빠졌다 (11/17). 세로줄 인용구 줄은 원래 왼쪽 정렬이다 (여자친구 글도 같음).
        """
        try:
            body_el.click(force=True); time.sleep(1)
            page.keyboard.press("Control+a"); time.sleep(1.5)
            frame.locator("button.se-font-size-code-toolbar-button").first.click()
            time.sleep(0.8)
            frame.locator(f"button[data-name='font-size'][data-value='{QUOTE_FONT_SIZE}']").first.click()
            time.sleep(1)
            frame.locator("button[data-name='align-drop-down-with-justify']").first.click()
            time.sleep(1)
            for sel in ("button[data-name='align-center']", "button[data-value='center']",
                        "button[class*='align-center']"):
                btn = frame.locator(sel)
                visible = [btn.nth(k) for k in range(btn.count()) if btn.nth(k).is_visible()]
                if visible:
                    visible[0].click()
                    break
            else:
                print("   ⚠️ 정렬 드롭다운에서 '가운데'를 찾지 못했습니다")
                self._snap(page, "align_dropdown", frame)
            time.sleep(1.5)
            page.keyboard.press("ArrowDown")
        except Exception as e:
            print(f"   ⚠️ 가운데 정렬 실패: {e}")
            self._snap(page, "align_fail", frame)
        left = frame.locator(".se-text-paragraph-align-left").count()
        total = frame.locator(".se-text-paragraph").count()
        print(f"   ↔️ 가운데 정렬 확인: 왼쪽 정렬 문단 {left}/{total}")
        return left == 0

    def _insert_map(self, page, frame, place_name: str, address: str) -> bool:
        """'장소' 버튼으로 가게를 검색해 지도 블록을 넣는다. 실패하면 팝업을 닫고 False."""
        try:
            frame.locator("button[data-name='map']").first.click()
            search = frame.locator("input.react-autosuggest__input").first
            search.wait_for(state="visible", timeout=15000)
            # React 입력창이라 fill()로 값을 넣으면 검색이 실행되지 않는다. 사람처럼 치고 Enter (11/17 확인)
            search.click()
            page.keyboard.type(place_name, delay=80)
            time.sleep(0.5)
            page.keyboard.press("Enter")
            items = frame.locator("li.se-place-map-search-result-item")
            items.first.wait_for(state="visible", timeout=15000)
            texts = [items.nth(i).inner_text() for i in range(min(items.count(), 10))]
            pick = pick_place_result(texts, address)
            print(f"   🗺️ 장소 검색 결과 {len(texts)}개 중 {pick + 1}번째 선택: {texts[pick].splitlines()[0] if texts[pick] else ''}")
            item = items.nth(pick)
            item.hover(); time.sleep(0.5)
            item.locator("button.se-place-add-button").first.click()
            time.sleep(1)
            frame.locator("button.se-popup-button-confirm").first.click()
            time.sleep(3)
            return True
        except Exception as e:
            print(f"   ⚠️ 지도 넣기 실패 ({place_name}): {e}")
            self._snap(page, "map_fail", frame)
            try:
                close = frame.locator("button.se-popup-close-button").first
                if close.is_visible(): close.click()
            except Exception:
                pass
            return False

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

    def publish(self, title: str, blocks: list, image_paths: list[str] = [], images_data: list = [], facts: dict = {},
                max_retries: int = 3, save: bool = True) -> bool:
        """save=False면 저장 버튼을 누르지 않는다 (시험 모드: 편집기 HTML만 debug 파일로 남기고 닫는다)."""
        for attempt in range(max_retries):
            if attempt > 0:
                self._step(f"다시 시도하는 중 ({attempt + 1}/{max_retries})")
            print(f"🔄 [V2 봇 안정화] 네이버 자동 발행 시작 (시도 {attempt + 1}/{max_retries})")
            success = self._execute_publish(title, blocks, image_paths, images_data, facts, save=save)
            if success:
                return True
            if self.login_required:
                print("❌ [V2 봇] 로그인이 필요해서 다시 시도하지 않습니다. 로그인을 저장한 뒤 다시 발행해 주세요:")
                print(f"   {SAVE_LOGIN_COMMAND}")
                return False
            if attempt < max_retries - 1:
                print(f"⚠️ [V2 봇] 예외 발생. 트래픽 안정화를 위해 10초 대기 후 재시도합니다...")
                time.sleep(10)
        print("❌ [V2 봇] 모든 재시도가 실패했습니다. 포스팅을 중단합니다.")
        return False

    def _execute_publish(self, title: str, blocks: list, image_paths: list[str] = [], images_data: list = [], facts: dict = {},
                         save: bool = True) -> bool:
        print(f"🚀 [V2 인플루언서 콜라주 모드] Starting - Title: {title}")
        self.last_problems = []
        self.login_required = False
        self.last_error = ""

        # 데이터 정규화
        normalized_blocks = []
        for b in blocks:
            if hasattr(b, "model_dump"): normalized_blocks.append(b.model_dump())
            elif isinstance(b, dict): normalized_blocks.append(b)

        # 1. 로그인: 비밀번호를 넣지 않고, 사람이 한 번 직접 로그인해 저장한 로그인 상태를 쓴다 (naver_session.py)
        #    매번 자동 로그인하면 네이버 보안 확인에 걸려 글쓰기 화면이 로그인 페이지로 돌아갔다 (2026-11-17).
        #    11/19: 로그인 저장과 같은 Chrome 프로필로 열어 네이버에 매번 같은 기기로 보이게 한다.
        if not has_saved_login():
            print("❌ 저장된 네이버 로그인이 없습니다. 먼저 로그인을 저장해 주세요:")
            self.last_error = "저장된 네이버 로그인이 없습니다"
            self.login_required = True
            return False

        self._step("네이버 글쓰기 화면 여는 중")
        with sync_playwright() as p:
            context = open_browser(p)
            page = first_page(context)
            Stealth().apply_stealth_sync(page)

            try:
                # 2. Access Editor (로그인 판단 = 글쓰기 화면이 실제로 열렸는지)
                page.goto(f"https://blog.naver.com/{self.naver_blog_id}?Redirect=Write&")
                page.wait_for_load_state("domcontentloaded")
                if is_login_page(page.url):
                    print("❌ 저장된 로그인이 만료됐습니다. 다시 로그인을 저장해 주세요:")
                    self.last_error = "저장된 네이버 로그인이 만료됐습니다"
                    self.login_required = True
                    return False
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
                problems = []  # 제대로 넣지 못한 블록 (조용히 넘어가지 않고 마지막에 알린다)

                # 블록 사이 간격 (2026-11-17): 여자친구 글은 블록 사이 빈 줄이 0줄이다 (편집기 기본 여백만).
                # 예전에는 블록마다 Enter를 3~4번 눌러 빈 줄이 3개씩 생겼다.
                # 이제 블록을 넣은 뒤에는 Enter를 누르지 않고, 글을 쓰기 직전에만 새 줄이 필요하면 1번 누른다.
                # 사진·지도·인용구는 커서 다음 자리에 들어가므로 앞에서 Enter를 누르지 않는다.
                prev_type = None

                for i, block in enumerate(normalized_blocks):
                    self._step(f"글 넣는 중 ({i + 1}/{len(normalized_blocks)})")
                    b_type = block.get("type", "text")
                    b_value = block.get("value") or ""
                    indices = block_image_indices(block)
                    
                    print(f"🧩 [{i+1}/{len(normalized_blocks)}] Block: {b_type}")

                    if b_type == "text" and b_value:
                        if prev_type is not None:
                            page.keyboard.press("Enter")  # 앞 블록 다음에 새 줄 하나
                        page.keyboard.type(b_value, delay=30)
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
                            
                            
                            # 커서를 글 끝(방금 넣은 사진)으로 옮긴다. 빈 줄은 만들지 않는다.
                            body_el.click(force=True)
                            page.keyboard.press("Control+End")
                        except Exception as e:
                            failed_image_indices.extend(indices)
                            print(f"   ⚠️ 사진 {indices} 업로드 실패: {e}")
                            self._snap(page, f"image_fail_{i}", frame)

                    elif b_type == "quote" and b_value:
                        if not self._insert_quote(page, frame, b_value, block.get("style") or "default"):
                            problems.append(f"인용구 {i + 1}번 블록")
                            continue
                        # 인용구 글 → 출처 칸 → 인용구 밖으로 빠져나온다 (Enter는 다음 글을 쓸 때 누른다)
                        page.keyboard.press("ArrowDown")
                        time.sleep(0.5)
                        page.keyboard.press("ArrowDown")
                        time.sleep(1)

                    elif b_type == "map" and b_value:
                        # 지도 뒤에서는 커서를 옮기지 않는다. 지도에는 글자 칸이 없어서 Ctrl+End를 누르면
                        # 커서가 앞 인용구 안으로 돌아가, 다음 인용구가 지도 앞에 들어갔다 (11/17 시험).
                        if not self._insert_map(page, frame, b_value, (facts or {}).get("address", "")):
                            problems.append(f"지도 {i + 1}번 블록")

                    elif b_type == "divider":
                        frame.locator("button[data-name='horizontal-line']").first.click(force=True)
                        time.sleep(2)
                        page.keyboard.press("ArrowDown")

                    if b_type in ("text", "image", "quote", "map", "divider"):
                        prev_type = b_type

                # 7. 안 쓴 사진은 올리지 않는다 (2026-11-17)
                # 예전에는 블록에 없는 사진을 글 끝에 모두 올렸는데, AI가 일부러 뺀 영수증 사진까지 올라갔다.
                # 빠뜨린 사진은 글쓰기 단계(sanitize_images)가 '뺀 사진'으로 보고하고 앱에서 다시 넣는다.
                skipped = unused_image_indices(normalized_blocks, len(image_paths))
                if skipped:
                    print(f"   🚫 글에 없는 사진 {skipped}은 올리지 않았습니다")
                if failed_image_indices:
                    print(f"   ⚠️ 업로드에 실패한 사진 {failed_image_indices}: 임시저장 글에서 직접 확인해 주세요")
                if problems:
                    print(f"   ⚠️ 제대로 넣지 못한 블록: {problems}")

                # 8. Align Center
                # 정렬 버튼이 드롭다운 하나로 바뀌어 예전 코드는 정렬을 하지 못했다 (11/17 확인).
                # 예전 테스트 블로그는 블로그 기본 정렬이 가운데라 된 것처럼 보였다. 여자친구 글은 거의 모두 가운데.
                self._align_all_center(page, frame, body_el)

                self._step("저장 전 자가 검사 중")
                # 9. 저장 전 자가 검사 (11/18): 편집기 HTML을 초안 블록과 비교한다.
                # '저장을 눌렀다'만으로는 성공이 아니었다 (11/17 정렬·글씨 크기가 적용 안 된 것을 손으로 비교해 찾음).
                try:
                    problems += check_editor_html(frame.content(), normalized_blocks, len(image_paths))
                except Exception as e:
                    problems.append(f"자가 검사를 하지 못했습니다: {e}")
                self.last_problems = problems
                if problems:
                    print("=" * 60)
                    print(f"⚠️ 저장 전 자가 검사: 고칠 것 {len(problems)}개 (임시저장은 합니다, 폰에서 확인해 주세요)")
                    for p in problems:
                        print(f"   - {p}")
                    print("=" * 60)
                else:
                    print("✅ 저장 전 자가 검사 통과: 블록 순서·줄·빈 줄·정렬·글씨 크기·사진·지도 모두 초안과 같습니다")

                # 10. Save
                self._step("임시저장 중")
                self._snap(page, "before_save", frame)  # 저장 직전 상태 (편집기 구조 확인용)
                if not save:
                    print("🧪 시험 모드: 저장하지 않고 닫습니다 (편집기 HTML은 debug 파일로 남김)")
                    return True
                page.evaluate("window.scrollTo(0, 0)"); time.sleep(3)
                save_btn = frame.locator("button:has-text('저장'), .save_btn__bzc5B").first
                if save_btn.is_visible():
                    save_btn.click(force=True)
                    print("✅ Mission Accomplished!")
                    time.sleep(5)  # 프로필 브라우저라 늘어난 로그인 유효기간은 닫을 때 저절로 저장된다
                    return True
                print("❌ 저장 버튼을 찾지 못했습니다")
                self.last_error = "편집기에서 저장 버튼을 찾지 못했습니다"
                self._snap(page, "no_save_button", frame)
                return False

            except Exception as e:
                print(f"❌ V2 Error: {e}")
                self.last_error = f"발행 중 오류: {str(e).splitlines()[0] if str(e) else type(e).__name__}"
                self._snap(page, "error", locals().get("frame"))
                return False
            finally:
                time.sleep(2); context.close()

naver_automation_v2 = NaverBlogAutomationV2()
