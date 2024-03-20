from typing import Annotated

import limits
import redis.asyncio as redis
from beanie import Link, PydanticObjectId
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi_oauth2.security import OAuth2
from jose import jwt
from limits.aio.strategies import RateLimiter
from pydantic import ValidationError
from starlette import status
from starlette.requests import Request

from app import config, crud, enums, models
from app.limits import rate_limiter, redis_client

reusable_oauth2 = OAuth2(auto_error=False)
api_key_header = APIKeyHeader(
    name="X-API-Key",
    description="API Key for authentication, generate one in /auth/api_key/generate.",
    scheme_name="X-API-Key",
)


class NotAuthenticatedError(Exception):
    pass


def get_current_active_user_fn(dependency):
    def f(current_user: Annotated[models.User, Security(dependency)]):
        if not crud.user.is_active(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
        return current_user

    return f


def get_current_active_superuser_fn(dependency, custom_message: str | None = None):
    def f(current_user: Annotated[models.User, Security(dependency)]):
        if not crud.user.is_superuser(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not superuser" if custom_message is None else custom_message,
            )
        return current_user

    return f


async def get_current_user_api_key(key: Annotated[str, Security(api_key_header)]) -> models.User:
    user_key = await crud.api_key.get_by_key(key=key)
    if user_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key for your user not found.",
        )
    return user_key.user  # type: ignore


get_current_active_user_api_key = get_current_active_user_fn(get_current_user_api_key)
get_current_active_superuser_api_key = get_current_active_superuser_fn(get_current_user_api_key)


def get_api_key_user_dependency_for_current_phase(*phases: enums.CompetitionPhase):
    """If the current phase does not equal the required phase, return the superuser dependency, else return the user
    dependency."""
    if config.settings.comp_phase in phases:
        return get_current_active_user_api_key
    return get_current_active_superuser_fn(
        get_current_user_api_key,
        f"This endpoint is not active for the current phase ('{config.settings.comp_phase.value}').",
    )


def get_user_dependency_for_current_phase(*phases: enums.CompetitionPhase):
    """If the current phase does not equal the required phase, return the superuser dependency, else return the user
    dependency."""
    if config.settings.comp_phase in phases:
        return get_current_active_user
    return get_current_active_superuser_fn(
        get_current_user, f"This endpoint is not active for the current phase ('{config.settings.comp_phase.value}')."
    )


async def get_current_user(request: Request, key: Annotated[str, Security(reusable_oauth2)]) -> models.User:
    if key is None:
        raise NotAuthenticatedError()
    try:
        payload = request.auth.jwt_decode(key.split("Bearer ")[1])
    except (jwt.JWTError, ValidationError) as e:
        raise NotAuthenticatedError() from e
    if "id" in payload:
        user_id = f"{request.auth.provider.provider}:{payload['id']}"
    else:
        user_id = f"{request.auth.provider.provider}:{payload['sub']}"
    user = await crud.user.get_by_openid_id(openid_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


get_current_active_user = get_current_active_user_fn(get_current_user)
get_current_active_superuser = get_current_active_superuser_fn(get_current_user)


def get_rate_limiter() -> RateLimiter:
    return rate_limiter


def get_redis_client() -> redis.Redis:
    return redis_client


def rate_limit_user(limit: str):
    parsed_limit = limits.parse(limit)

    async def f(
        request: Request,
        current_user: Annotated[models.User, Depends(get_current_active_user_api_key)],
        limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    ) -> models.User:
        should_limit = not await limiter.hit(parsed_limit, request.url.path, current_user.openid_id)
        if should_limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
        return current_user

    return f


def get_user_object_fn(object_crud: crud.CRUDDefense | crud.CRUDChat, allow_team: bool = False):
    async def f(id: PydanticObjectId, current_user: Annotated[models.User, Depends(get_current_active_user_api_key)]):
        fetched_object = await object_crud.get(id=id)
        if fetched_object is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
        await fetched_object.fetch_all_links()
        await fetched_object.user.fetch_all_links()  # type: ignore
        await current_user.fetch_all_links()

        object_is_owned_by_user_team = (
            current_user.team is not None
            and fetched_object.user.team is not None  # type: ignore
            and current_user.team.id == fetched_object.user.team.id  # type: ignore
        )
        if allow_team and object_is_owned_by_user_team:  # type: ignore
            await fetched_object.user.team.fetch_all_links()  # type: ignore
            user_team = await Link.fetch_list(fetched_object.user.team.users, fetch_links=True)  # type: ignore
            user_team_ids = {user.id for user in user_team}
        else:
            user_team_ids = {current_user.id}
        object_owner_id = fetched_object.user.id  # type: ignore
        if object_owner_id not in user_team_ids and not crud.user.is_superuser(current_user):  # type: ignore
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="You don't have the permission to see this object."
            )
        return fetched_object

    return f


get_chat = get_user_object_fn(crud.chat)
get_defense = get_user_object_fn(crud.defense, allow_team=True)


ChatDep = Annotated[models.Chat, Depends(get_chat)]
ActiveUserAPIKeyDep = Annotated[models.User, Depends(get_current_active_user_api_key)]
ActiveSuperUserAPIKeyDep = Annotated[models.User, Depends(get_current_active_superuser_api_key)]
ActiveUserBearerDep = Annotated[models.User, Depends(get_current_active_user)]
ActiveSuperUserDep = Annotated[models.User, Depends(get_current_active_superuser)]
