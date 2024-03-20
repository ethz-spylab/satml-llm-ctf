from typing import Any, Generic, TypeVar

from beanie import Document, PydanticObjectId
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

ModelType = TypeVar("ModelType", bound=Document)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDError(Exception):
    pass


class DefenseNotFoundError(CRUDError):
    pass


class TeamNotFoundError(CRUDError):
    pass


class ChatNotFoundError(CRUDError):
    pass


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).

        **Parameters**

        * `model`: A Beanie model class
        """
        self.model = model

    async def get(self, id: Any) -> ModelType | None:
        return await self.model.get(id, fetch_links=True)

    async def get_multi(self, *, skip: int = 0, limit: int = 100) -> list[ModelType]:
        return await self.model.find_many(fetch_links=True).skip(skip).limit(limit).to_list()

    async def create(self, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)  # type: ignore
        await db_obj.create()
        return db_obj

    async def update(self, *, db_obj: ModelType, obj_in: UpdateSchemaType | dict[str, Any]) -> ModelType:
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        await db_obj.save()
        return db_obj

    async def remove(self, *, id: PydanticObjectId) -> ModelType | None:
        obj = await self.model.get(id)
        if obj is None:
            return None
        await obj.delete()
        return obj
