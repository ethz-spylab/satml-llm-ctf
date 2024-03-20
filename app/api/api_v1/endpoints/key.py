"""This is an example usage of fastapi-sso.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from starlette import status

from app import schemas, security
from app.api import deps
from app.config import settings
from app.crud import api_key as crud_api_key

router = APIRouter()


@router.get("/generate", response_model=schemas.NewAPIKeyResponse)
async def create_api_key(current_user: deps.ActiveUserBearerDep) -> schemas.NewAPIKeyResponse:
    key = security.create_api_key()
    try:
        key_in_db = await crud_api_key.create(obj_in=schemas.APIKeyCreate(key=key, user=current_user.id))
    except ValueError:
        url = f"{settings.base_url}{settings.api_v1_str}{router.prefix}/key/revoke"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"You already have an API key. To revoke the existing one, use {url}. Then call this endpoint again."
            ),
        )
    return schemas.NewAPIKeyResponse(key=key, created=key_in_db.created)


@router.get("/revoke")
async def revoke_api_key(current_user: deps.ActiveUserBearerDep):
    assert current_user.id is not None
    user_key = await crud_api_key.get_by_user(user_id=current_user.id)
    if user_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    await user_key.delete()
    return JSONResponse({"detail": "API key revoked."})
