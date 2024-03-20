from collections.abc import Sequence

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from app import crud, schemas
from app.api import deps
from app.api.api_v1.endpoints import utils

router = APIRouter()


@router.get("/", response_model=Sequence[schemas.UserInfo])
async def read_users(
    _: deps.ActiveSuperUserAPIKeyDep,
    skip: int = 0,
    limit: int = 100,
) -> list[schemas.UserInfo]:
    """
    Retrieve users.
    """
    users = await crud.user.get_multi(skip=skip, limit=limit)
    [await user.fetch_all_links() for user in users]
    return [await utils.idfy_team(user) for user in users]


@router.get("/me", response_model=schemas.UserInfo)
async def read_user_me(
    current_user: deps.ActiveUserAPIKeyDep,
) -> schemas.UserInfo:
    """
    Get current user.
    """
    await current_user.fetch_all_links()
    return await utils.idfy_team(current_user)


@router.get("/{user_id}", response_model=schemas.UserInfo)
async def read_user_by_id(
    user_id: str,
    _: deps.ActiveSuperUserAPIKeyDep,
) -> schemas.UserInfo:
    """
    Get a specific user by id.
    """
    user = await crud.user.get(id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    await user.fetch_all_links()
    return await utils.idfy_team(user)


@router.post("/{user_id}/deactivate", dependencies=[Depends(deps.get_current_active_superuser_api_key)])
async def deactivate_user(user_id: PydanticObjectId) -> dict[str, str]:
    user = await crud.user.get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    await crud.user.deactivate_user(user)
    return {"info": "User deactivated successfully"}


@router.post("/{user_id}/activate", dependencies=[Depends(deps.get_current_active_superuser_api_key)])
async def activate_user(user_id: PydanticObjectId) -> dict[str, str]:
    user = await crud.user.get(user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    await crud.user.activate_user(user)
    return {"info": "User activated successfully"}
