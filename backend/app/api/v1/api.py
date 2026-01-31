from fastapi import APIRouter
from .endpoints import system, posts

api_router = APIRouter()

api_router.include_router(system.router, tags=["system"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
