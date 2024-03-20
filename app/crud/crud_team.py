from beanie import Link, PydanticObjectId
from pymongo.errors import DuplicateKeyError

from app import models, schemas

from .base import CRUDBase, CRUDError, ModelType


class CRUDTeam(CRUDBase[models.Team, schemas.TeamCreate, schemas.TeamUpdate]):
    async def create(self, *, obj_in: schemas.TeamCreate) -> models.Team:
        db_obj = self.model(name=obj_in.name, is_active=True, users=[])
        try:
            await db_obj.create()
        except DuplicateKeyError:
            raise CRUDError(f"Duplicate team name: team name '{obj_in.name}' already exists")
        return db_obj

    async def remove(self, *, id: PydanticObjectId) -> ModelType | None:  # type: ignore
        db_obj = await super().remove(id=id)
        if team is None:
            return None
        for user in await Link.fetch_list(db_obj.users):  # type: ignore
            user.team = None
            await user.save()
        return db_obj

    async def remove_by_name(self, *, name: str) -> models.Team | None:
        db_obj = await self.get_by_name(name=name)
        if db_obj is None:
            return None
        await db_obj.delete()
        for user in await Link.fetch_list(db_obj.users):  # type: ignore
            user.team = None
            await user.save()
        return db_obj

    async def get_by_name(self, *, name: str) -> models.Team | None:
        return await self.model.find_one(
            self.model.name == name,
            fetch_links=True,
        )

    async def get_or_create(self, *, obj_in: schemas.TeamCreate) -> models.Team:
        db_obj = await self.get_by_name(name=obj_in.name)
        if db_obj is not None:
            return db_obj
        return await self.create(obj_in=obj_in)

    async def add_user(self, *, user: models.User, team: models.Team) -> models.Team:
        if user.team is not None:
            raise ValueError("User already has a team")
        if user in team.users:
            return team
        team.users.append(user)  # type: ignore
        user.team = team
        await user.save()
        await team.save()
        return team

    async def remove_user(self, *, user: models.User, team: models.Team) -> models.Team:
        team.users = [u for u in team.users if u.id != user.id]  # type: ignore
        user.team = None
        await user.save()
        await team.save()
        return team

    @staticmethod
    def is_active(team: models.Team) -> bool:
        return team.is_active


team = CRUDTeam(models.Team)
