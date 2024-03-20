from app import models, schemas


async def idfy_team(user: models.User) -> schemas.UserInfo:
    await user.fetch_all_links()
    return schemas.UserInfo(
        id=user.id,
        openid_id=user.openid_id,
        team=user.team.id if user.team is not None else None,  # type: ignore
        provider=user.provider,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
    )
