from beanie import PydanticObjectId

from app import models, schemas

from .base import CRUDBase


class CRUDUser(CRUDBase[models.User, schemas.UserCreate, schemas.UserUpdate]):
    async def get_by_email(self, *, email: str) -> models.User | None:
        return await self.model.find_one(self.model.email == email)

    async def get_by_openid_id(self, *, openid_id: str) -> models.User | None:
        return await self.model.find_one(self.model.openid_id == openid_id)

    async def create(self, *, obj_in: schemas.UserCreate) -> models.User:
        db_obj = models.User(
            email=obj_in.email,
            openid_id=obj_in.openid_id,
            provider=obj_in.provider,
            team=None,
            is_superuser=False,
            is_active=True,
        )
        await db_obj.create()
        return db_obj

    async def get_or_create(self, *, obj_in: schemas.UserCreate) -> models.User:
        db_obj = await self.get_by_email(email=obj_in.email)
        if db_obj:
            return db_obj
        return await self.create(obj_in=obj_in)

    async def get_by_team(self, *, team_id: PydanticObjectId, skip: int = 0, limit: int = 100) -> list[models.User]:
        return (
            await self.model.find_many(self.model.team.id == team_id, fetch_links=True)  # type: ignore
            .skip(skip)
            .limit(limit)
            .to_list()
        )

    @staticmethod
    def is_active(user: models.User) -> bool:
        return user.is_active

    @staticmethod
    def is_superuser(user: models.User) -> bool:
        return user.is_superuser

    @staticmethod
    async def deactivate_user(user: models.User) -> models.User:
        user.is_active = False
        await user.save()
        return user

    @staticmethod
    async def activate_user(user: models.User) -> models.User:
        user.is_active = True
        await user.save()
        return user


user = CRUDUser(models.User)
