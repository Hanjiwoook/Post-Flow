from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar("T")

class CommonResponse(BaseModel, Generic[T]):
    """
    SRS 1. 공통 응답 규격
    {
        "success": true,
        "message": "요청 성공",
        "data": { ... },
        "error": null
    }
    """
    success: bool
    message: str
    data: Optional[T] = None
    error: Optional[Any] = None
