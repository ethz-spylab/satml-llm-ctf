from beanie import PydanticObjectId
from beanie.operators import Eq, In
from fastapi import HTTPException
from starlette import status

from app import models, schemas

from .base import CRUDBase
from .crud_defense import defense as crud_defense
from .crud_secret import secret as crud_secret
from .crud_user import user as crud_user


class CRUDChat(CRUDBase[models.Chat, schemas.ChatCreate, schemas.ChatUpdate]):
    async def create(self, *, obj_in: schemas.ChatCreate) -> models.Chat:
        defense = await crud_defense.get(obj_in.defense_id)
        user = await crud_user.get(obj_in.user_id)
        secret = await crud_secret.get(obj_in.secret_id)
        if defense is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Defense not found")
        db_obj = self.model(
            user=user,
            defense=defense,
            secret=secret,
            model=obj_in.model,
            is_attack=obj_in.is_attack,
            is_evaluation=obj_in.is_evaluation,
        )
        await db_obj.create()
        return db_obj

    async def get_by_user(
        self,
        *,
        user_id: PydanticObjectId,
        skip: int = 0,
        limit: int = 100,
        attack: bool = False,
        evaluation: bool = False,
    ) -> list[models.Chat]:
        return await self.model.find_many(
            self.model.user.id == user_id,  # type: ignore
            Eq(self.model.is_attack, attack),
            Eq(self.model.is_evaluation, evaluation),
            fetch_links=True,
            skip=skip,
            limit=limit,
        ).to_list()

    @staticmethod
    async def append(db_obj: models.Chat, obj_in: schemas.ChatUpdate, save: bool) -> models.Chat:
        if db_obj is None:
            raise ValueError(f"Chat with id {obj_in.id} not found")
        db_obj.history.append(obj_in.message)
        if save:
            await db_obj.save()
            await db_obj.fetch_all_links()
        return db_obj

    async def get_n_eval_chats_by_team_and_submission(
        self, submission: models.DefenseSubmission, user_ids: set[PydanticObjectId]
    ) -> int:
        return await self.model.find_many(
            In(self.model.user.id, user_ids),  # type: ignore
            self.model.defense.id == submission.defense.id,  # type: ignore
            self.model.model == submission.model,
            Eq(self.model.is_evaluation, True),
            fetch_links=True,
        ).count()


chat = CRUDChat(models.Chat)
