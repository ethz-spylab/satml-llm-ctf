from typing import Any

from beanie import PydanticObjectId
from beanie.odm.operators.find.comparison import Eq

from app import models, schemas

from . import crud_defense
from .base import CRUDBase, CRUDError, DefenseNotFoundError


class TooManySecretAttemptsError(Exception):
    pass


class AllSecretsGuessedError(CRUDError):
    pass


class CRUDSecret(CRUDBase[models.Secret, schemas.SecretCreate, schemas.SecretUpdate]):
    async def update(self, *, db_obj: models.APIKey, obj_in: schemas.SecretUpdate | dict[str, Any]) -> models.Secret:
        raise NotImplementedError("Can't update a secret")

    async def create(self, *, obj_in: schemas.SecretCreate) -> models.Secret:
        if obj_in.submission_id is None:
            submission = None
        else:
            submission = await crud_defense.defense.get_submission_by_id(id=obj_in.submission_id)
            if submission is None:
                raise DefenseNotFoundError("Submission not found")
        db_obj = self.model(
            value=obj_in.value,
            submission=submission,
            is_evaluation=obj_in.is_evaluation,
            evaluation_index=obj_in.evaluation_index,
        )
        await db_obj.create()
        await db_obj.fetch_all_links()
        return db_obj

    async def get_by_chat_id(self, *, chat_id: PydanticObjectId) -> list[models.Secret]:
        return await self.model.find(self.model.chat_id == chat_id, fetch_links=True).to_list()

    async def get_by_submission(self, *, submission_id: PydanticObjectId) -> list[models.Secret]:
        return await self.model.find(self.model.submission.id == submission_id, fetch_links=True).to_list()  # type: ignore

    async def remove_by_submission(self, *, submission_id: PydanticObjectId):
        await self.model.find(self.model.submission.id == submission_id).delete()  # type: ignore

    async def get_by_submission_and_index(self, *, submission_id: PydanticObjectId, index: int) -> models.Secret | None:
        return await self.model.find_one(
            self.model.submission.id == submission_id,  # type: ignore
            self.model.evaluation_index == index,
            fetch_links=True,
        )

    async def get_new_evaluation_secret(
        self, *, submission_id: PydanticObjectId, most_recent_guess_secret: models.Secret | None
    ) -> models.Secret:
        if most_recent_guess_secret is None:
            next_index = 0
        else:
            assert most_recent_guess_secret.evaluation_index is not None
            next_index = most_recent_guess_secret.evaluation_index + 1
        new_secret = await self.get_by_submission_and_index(submission_id=submission_id, index=next_index)
        if new_secret is None:
            raise AllSecretsGuessedError("All secrets have been guessed or exhausted")
        return new_secret

    async def get_evaluation_secrets(self, *, skip: int = 0, limit: int = 100) -> list[models.Secret]:
        return (
            await self.model.find_many(Eq(self.model.is_evaluation, True), fetch_links=True)
            .skip(skip)
            .limit(limit)
            .to_list()
        )


secret = CRUDSecret(models.Secret)
