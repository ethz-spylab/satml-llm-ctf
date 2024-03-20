from typing import Any

from beanie import PydanticObjectId

from app import models, schemas

from .base import CRUDBase


class CRUDAPIKey(CRUDBase[models.APIKey, schemas.APIKeyCreate, schemas.APIKeyUpdate]):
    async def update(self, *, db_obj: models.APIKey, obj_in: schemas.APIKeyUpdate | dict[str, Any]) -> models.APIKey:
        raise NotImplementedError("Can't update API keys")

    async def create(self, *, obj_in: schemas.APIKeyCreate) -> models.APIKey:
        if await self.get_by_user(user_id=obj_in.user):
            raise ValueError("User already has an API key")
        return await super().create(obj_in=obj_in)

    async def get_by_user(self, *, user_id: PydanticObjectId) -> models.APIKey | None:
        return await self.model.find_one(self.model.user.id == user_id, fetch_links=True)  # type: ignore

    async def get_by_key(self, *, key: str) -> models.APIKey | None:
        db_obj = await self.model.find_one(self.model.key == key, fetch_links=True)
        if db_obj is not None:
            await db_obj.fetch_all_links()
        return db_obj


api_key = CRUDAPIKey(models.APIKey)
