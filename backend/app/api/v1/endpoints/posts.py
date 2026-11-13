from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from typing import List, Optional # Optional 추가
from PIL import Image
import io
import os
import uuid
import shutil
from sqlalchemy.orm import Session

from ....services.gemini_service import gemini_service
from ....services.llm_client import LLMError
from ....services.post_writer import write_post
from ....services.post_reviewer import review_post
from ....schemas.review import ReviewRequest, ReviewResult
from ....services.automation.naver_v2 import naver_automation_v2
from ....services.automation.tistory import tistory_automation
from ....schemas.post import AnalyzeResult, PostPublishRequest, JobResponse, PostResponse, RefineRequest, PatchRequest
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
        
        # 만약 result.images가 비어있다면 (Gemini가 안 채워줬을 경우 대비)
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

@router.post("/refine", response_model=CommonResponse[AnalyzeResult])
async def refine_post(
    request: RefineRequest
):
    """
    수정된 팩트 정보 및 사용자 요청사항을 바탕으로 본문 내용을 재구성함
    """
    try:
        result = await gemini_service.refine_content(
            request.title,
            request.content,
            request.blocks,  # 현재 본문 블록 전달 (부분 수정용)
            request.facts,
            request.style,
            request.images, # 이미지 데이터 전달 추가
            request.instruction,
            request.template_name
        )
        return CommonResponse(
            success=True,
            message="본문 재구성 성공",
            data=result
        )
    except Exception as e:
        return CommonResponse(
            success=False,
            message="본문 재구성 중 오류가 발생했습니다.",
            error=str(e)
        )

@router.post("/patch", response_model=CommonResponse[AnalyzeResult])
async def patch_post(
    request: PatchRequest
):
    """
    팩트 정보만 바꿨을 때 특정 섹션만 초고속으로 갈아 끼움
    """
    try:
        updated_blocks = await gemini_service.patch_sections(
            request.blocks,
            request.facts
        )
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

# 실제 발행을 수행하는 백그라운드 함수
def run_publish_job(post_id: int, title: str, blocks: list, image_paths: List[str], images_data: list, facts: dict, platform: str, db_session: Session):
    success = False
    post_url = None
    
    if platform.upper() == "NAVER":
        # 네이버 발행 (블록 방식 + 이미지 카테고리 + 팩트 정보 적용)
        success = naver_automation_v2.publish(title, blocks, image_paths, images_data, facts)
    elif platform.upper() == "TISTORY":
        # 티스토리 발행 (기존 방식 유지하되 텍스트만 추출)
        content = "\n".join([b.get("value", "") for b in blocks if b.get("type") == "text" or b.get("type") == "quote"])
        post_url = tistory_automation.publish(title, content, image_paths)
        success = True if post_url else False
    
    # DB 상태 업데이트
    from ....db.session import SessionLocal
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if post:
            post.status = "SUCCESS" if success else "FAIL"
            if post_url:
                post.post_url = post_url
            db.commit()
    finally:
        db.close()

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
