from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from typing import List, Optional # Optional 추가
from PIL import Image
import io
import os
import uuid
import shutil
from sqlalchemy.orm import Session

from ....services.llm_client import LLMError
from ....services.post_writer import write_post
from ....services.post_reviewer import review_post
from ....schemas.review import ReviewRequest, ReviewResult
from ....services.post_reviser import revise_post
from ....schemas.revise import ReviseRequest, ReviseResult
from ....services.memo_editor import suggest_memo_edits
from ....schemas.memo_edit import MemoEditRequest, MemoEditResult
from ....services.automation.naver_v2 import naver_automation_v2
from ....services.automation.tistory import tistory_automation
from ....schemas.post import AnalyzeResult, ContentBlock, PostPublishRequest, JobResponse, PostResponse, PublishStatus, PatchRequest
from ....schemas.common import CommonResponse
from ....db.session import get_db
from ....db.models import Post

router = APIRouter()

# 이미지 저장 경로 (절대 경로로 설정하여 실행 위치에 따른 중복 생성 방지)
# 현재 파일: backend/app/api/v1/endpoints/posts.py
# 목표 경로: backend/uploads
current_dir = os.path.dirname(os.path.abspath(__file__)) # endpoints/
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))) # backend/
UPLOAD_DIR = os.path.join(backend_dir, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/analyze", response_model=CommonResponse[AnalyzeResult])
async def analyze_post(
    files: List[UploadFile] = File(...),
    style: str = Form("emotional"),
    template_name: Optional[str] = Form(None),
    initial_facts: Optional[str] = Form(None) # JSON 문자열로 받음
):
    """
    SRS 2.2 이미지 분석 및 초안 생성 API
    """
    if len(files) > 50:
        return CommonResponse(success=False, message="이미지는 최대 50장까지만 가능합니다.", error="TOO_MANY_IMAGES")

    try:
        # initial_facts 파싱
        facts_dict = {}
        if initial_facts:
            import json
            try:
                facts_dict = json.loads(initial_facts)
            except:
                pass

        saved_image_paths = []
        pil_images = []

        # ... (중간 생략: 이미지 저장 로직)
        for file in files:
            extension = file.filename.split(".")[-1]
            unique_filename = f"{uuid.uuid4()}.{extension}"
            file_path = os.path.join(UPLOAD_DIR, unique_filename)
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
                image = Image.open(io.BytesIO(content))
                pil_images.append(image)
            abs_path = os.path.abspath(file_path)
            saved_image_paths.append(abs_path)
        
        # Claude 글쓰기 (사진 + 앱이 보낸 가게 정보 원본). style은 더 이상 쓰지 않는다.
        result = await write_post(pil_images, facts_dict)
        result.template_name = template_name

        # 결과에 이미지 정보 업데이트 (저장된 경로 및 카테고리 매칭)
        # AnalyzeResult의 images 리스트에 저장된 실제 경로(path)를 채워줌
        for i, img_info in enumerate(result.images):
            if i < len(saved_image_paths):
                img_info.path = saved_image_paths[i]
        
        # 만약 result.images가 비어있다면 (AI 결과에 사진 정보가 없을 경우 대비)
        if not result.images and saved_image_paths:
            from ....schemas.post import ImageInfo
            for path in saved_image_paths:
                result.images.append(ImageInfo(path=path, category="FOOD_MAIN"))

        # 하위 호환성을 위해 기존 리스트도 유지
        result.image_paths = saved_image_paths
        
        return CommonResponse(
            success=True,
            message="이미지 분석 성공",
            data=result
        )

    except LLMError as e:
        # 키 없음, 크레딧 부족, 거절 등. 사용자에게 보여 줄 수 있는 한국어 메시지다.
        return CommonResponse(success=False, message=str(e), error="LLM_ERROR")
    except Exception as e:
        return CommonResponse(
            success=False,
            message="AI 분석 중 오류가 발생했습니다.",
            error=str(e)
        )

@router.post("/review", response_model=CommonResponse[ReviewResult])
async def review_draft(request: ReviewRequest):
    """
    파워블로거 검수: 초안의 점수, 문제점, 빠진 정보, 사용자에게 할 질문을 돌려준다.
    글은 고치지 않는다 (고쳐 쓰기는 사용자 답변을 받은 뒤 별도 단계).
    """
    try:
        result = await review_post(request.title, request.blocks, request.facts,
                                   request.images, request.writing_notes)
        return CommonResponse(success=True, message="검수 완료", data=result)
    except LLMError as e:
        return CommonResponse(success=False, message=str(e), error="LLM_ERROR")
    except Exception as e:
        return CommonResponse(success=False, message="검수 중 오류가 발생했습니다.", error=str(e))

@router.post("/revise", response_model=CommonResponse[ReviseResult])
async def revise_draft(request: ReviseRequest):
    """
    검수 반영 고쳐쓰기: 초안 + 검수 결과 + 사용자 답변 → 고친 글.
    text 블록만 바뀌고 사진·지도·인용구 블록은 그대로다. 요청 1번에 AI 호출 1번.
    """
    try:
        result = await revise_post(request.title, request.blocks, request.facts, request.images,
                                   request.writing_notes, request.review, request.answers)
        return CommonResponse(success=True, message="고쳐쓰기 완료", data=result)
    except LLMError as e:
        return CommonResponse(success=False, message=str(e), error="LLM_ERROR")
    except Exception as e:
        return CommonResponse(success=False, message="고쳐쓰기 중 오류가 발생했습니다.", error=str(e))

@router.post("/memo-edit", response_model=CommonResponse[MemoEditResult])
async def memo_edit(request: MemoEditRequest):
    """
    메모로 부분 고치기: 메모마다 고친 안(원래 → 고친 글)과 의견을 돌려준다.
    글은 바꾸지 않는다. 승인은 앱에서 하고, 승인할 때 AI를 다시 부르지 않는다.
    """
    try:
        result = await suggest_memo_edits(request.title, request.blocks, request.facts, request.images,
                                          request.writing_notes, request.memos, request.answers)
        return CommonResponse(success=True, message="고친 안 완료", data=result)
    except LLMError as e:
        return CommonResponse(success=False, message=str(e), error="LLM_ERROR")
    except Exception as e:
        return CommonResponse(success=False, message="고친 안을 만드는 중 오류가 발생했습니다.", error=str(e))

PLACE_INFO_MARK = "[매장 위치 & 정보]"


def patch_sections(current_blocks: List[ContentBlock], new_facts: dict) -> List[ContentBlock]:
    """가게 정보를 바꿨을 때 '[매장 위치 & 정보]' 인용구만 새 정보로 갈아 끼운다 (AI 호출 없음).

    11/19: gemini_service.py를 지우면서 여기로 옮겼다 (원래부터 Gemini를 쓰지 않는 글자 바꾸기였다).
    지금 글쓰기(post_writer)는 이 표시를 쓰지 않아서 새 글에서는 바뀌는 블록이 없다.
    앱에서도 이 API를 부르는 화면(_showEditInfoModal)이 쓰이지 않는다 → 0단계 '정리'에서 함께 정리할 것.
    """
    info = (f"{new_facts.get('place_name', '매장')} / {new_facts.get('address', '주소')} / "
            f"{new_facts.get('business_hours', '시간')} / {new_facts.get('phone', '번호')} / {new_facts.get('parking', '주차')}")
    return [ContentBlock(type="quote", value=f"{PLACE_INFO_MARK} {info}") if PLACE_INFO_MARK in (b.value or "") else b
            for b in current_blocks]


@router.post("/patch", response_model=CommonResponse[AnalyzeResult])
async def patch_post(
    request: PatchRequest
):
    """
    팩트 정보만 바꿨을 때 특정 섹션만 초고속으로 갈아 끼움
    """
    try:
        updated_blocks = patch_sections(request.blocks, request.facts)
        # 결과 반환 (AnalyzeResult 형식에 맞춰서)
        return CommonResponse(
            success=True,
            message="섹션 부분 업데이트 성공",
            data=AnalyzeResult(
                title=request.title,
                content="",
                blocks=updated_blocks,
                tags=[], # 기존 태그 유지 로직 필요시 추가
                facts=request.facts,
                images=request.images
            )
        )
    except Exception as e:
        return CommonResponse(
            success=False,
            message="부분 업데이트 중 오류가 발생했습니다.",
            error=str(e)
        )

# 발행 실패 종류 (앱이 보고 안내를 고른다)
LOGIN_REQUIRED = "LOGIN_REQUIRED"  # 저장된 로그인이 없거나 만료됨 → 로그인 저장 명령을 안내
PUBLISH_ERROR = "PUBLISH_ERROR"    # 그 밖의 실패


def _update_post(post_id: int, **fields):
    """발행 작업은 요청이 끝난 뒤 백그라운드에서 돌아서, 요청의 DB 세션 대신 새 세션으로 쓴다."""
    from ....db.session import SessionLocal
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            for key, value in fields.items():
                setattr(post, key, value)
            db.commit()
    finally:
        db.close()


# 실제 발행을 수행하는 백그라운드 함수
# 6-4 (11/19): 결과(성공/실패, 실패 이유, 자가 검사 '고칠 것')와 진행 단계를 DB에 적어 앱이 볼 수 있게 한다.
def run_publish_job(post_id: int, title: str, blocks: list, image_paths: List[str], images_data: list, facts: dict, platform: str, db_session: Session):
    success = False
    post_url = None
    error_code = None
    fail_reason = None
    problems = []

    try:
        if platform.upper() == "NAVER":
            bot = naver_automation_v2
            bot.on_step = lambda text: _update_post(post_id, step=text)
            try:
                # 네이버 발행 (블록 방식 + 이미지 카테고리 + 팩트 정보 적용)
                success = bot.publish(title, blocks, image_paths, images_data, facts)
            finally:
                bot.on_step = None
            problems = list(bot.last_problems)
            if not success:
                error_code = LOGIN_REQUIRED if bot.login_required else PUBLISH_ERROR
                fail_reason = bot.last_error or "발행에 실패했습니다 (서버 로그를 확인해 주세요)"
        elif platform.upper() == "TISTORY":
            # 티스토리 발행 (기존 방식 유지하되 텍스트만 추출)
            content = "\n".join([b.get("value", "") for b in blocks if b.get("type") == "text" or b.get("type") == "quote"])
            post_url = tistory_automation.publish(title, content, image_paths)
            success = True if post_url else False
            if not success:
                error_code, fail_reason = PUBLISH_ERROR, "티스토리 발행에 실패했습니다"
        else:
            error_code, fail_reason = PUBLISH_ERROR, f"지원하지 않는 플랫폼입니다: {platform}"
    except Exception as e:
        # 여기서 멈추면 DB가 PROCESSING으로 남아 앱이 끝없이 기다리므로, 실패로 적고 끝낸다
        print(f"❌ 발행 작업 오류: {e}")
        success, error_code, fail_reason = False, PUBLISH_ERROR, f"발행 중 예상하지 못한 오류: {e}"

    fields = dict(status="SUCCESS" if success else "FAIL", step=None,
                  error_code=error_code, fail_reason=fail_reason, problems=problems)
    if post_url:
        fields["post_url"] = post_url
    _update_post(post_id, **fields)

@router.post("/publish", response_model=CommonResponse[JobResponse])
async def publish_post(
    request: PostPublishRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    SRS 2.3 포스팅 최종 발행 요청
    """
    job_ids = []
    for platform in request.platforms:
        # 1. DB에 'PROCESSING' 상태로 기록 (모든 정보 포함)
        new_post = Post(
            title=request.final_title,
            content=request.final_content,
            template_name=request.template_name, # 추가
            blocks=[b.dict() for b in request.blocks], # 블록 저장
            image_paths=request.image_paths,
            images_data=[img.dict() for img in request.images], # 상세 이미지 정보 저장
            tags=request.tags,
            facts=request.facts,
            platform=platform.upper(),
            status="PROCESSING"
        )
        db.add(new_post)
        db.commit()
        db.refresh(new_post)
        job_ids.append(str(new_post.id))

        # 2. 백그라운드 작업 등록 (facts 포함)
        background_tasks.add_task(
            run_publish_job, 
            new_post.id, 
            request.final_title, 
            [b.dict() for b in request.blocks], 
            request.image_paths, 
            [img.dict() for img in request.images], 
            request.facts, # 팩트 정보 전달 (지도 검색용)
            platform,
            db
        )
    
    return CommonResponse(
        success=True,
        message="발행 작업이 시작되었습니다.",
        data=JobResponse(
            job_id=", ".join(job_ids),
            status="PROCESSING"
        )
    )

@router.get("/{post_id}/status", response_model=CommonResponse[PublishStatus])
async def get_publish_status(post_id: int, db: Session = Depends(get_db)):
    """발행 결과 창(6-4)이 몇 초마다 묻는 발행 상태. PROCESSING이 끝날 때까지 step이 바뀐다."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return CommonResponse(success=False, message="발행 기록을 찾지 못했습니다.", error=f"post_id={post_id}")
    return CommonResponse(
        success=True,
        message="발행 상태 조회 성공",
        data=PublishStatus(
            id=post.id, platform=post.platform, status=post.status, step=post.step,
            error_code=post.error_code, fail_reason=post.fail_reason,
            problems=post.problems or [], post_url=post.post_url,
        ),
    )

@router.get("/history", response_model=CommonResponse[List[PostResponse]])
async def get_history(db: Session = Depends(get_db)):
    """
    내 포스팅 이력 조회 API
    """
    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    
    # DB 모델의 images_data를 스키마의 images 필드로 매핑
    result = []
    for p in posts:
        post_dict = {c.name: getattr(p, c.name) for c in p.__table__.columns}
        post_dict['images'] = p.images_data
        result.append(post_dict)
        
    return CommonResponse(
        success=True,
        message="이력 조회 성공",
        data=result
    )
