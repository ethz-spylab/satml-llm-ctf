from fastapi import APIRouter

from app.config import ChatModel

router = APIRouter()


@router.get("/models", response_model=set[str])
def get_models() -> set[str]:
    return {m.value for m in ChatModel}
