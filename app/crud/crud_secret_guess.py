import asyncio
import datetime
from typing import Any

from beanie import PydanticObjectId
from beanie.odm.operators.find.comparison import Eq
from pydantic import BaseModel

from app import models, schemas

from .base import ChatNotFoundError, CRUDBase, CRUDError, DefenseNotFoundError, TeamNotFoundError
from .crud_chat import chat as crud_chat
from .crud_secret import secret as crud_secret
from .crud_team import team as crud_team

secret_guessing_lock = asyncio.Lock()


class InvalidGuessError(CRUDError):
    pass


class TimeStampProjection(BaseModel):
    timestamp: datetime.datetime


class CRUDSecretGuess(CRUDBase[models.SecretGuess, schemas.SecretGuessCreate, schemas.SecretGuessUpdate]):
    async def update(
        self, *, db_obj: models.APIKey, obj_in: schemas.SecretGuessUpdate | dict[str, Any]
    ) -> models.SecretGuess:
        raise NotImplementedError("Can't update a secret guess")

    async def remove_by_secret(self, *, secret_id: PydanticObjectId) -> None:
        await self.model.find_many(self.model.secret.id == secret_id).delete()  # type: ignore

    async def create(self, *, obj_in: schemas.SecretGuessCreate) -> models.SecretGuess:
        secret = await crud_secret.get(id=obj_in.secret_id)
        team = await crud_team.get(id=obj_in.guesser_id)
        chat = await crud_chat.get(id=obj_in.chat_id)
        if secret is None:
            raise DefenseNotFoundError("Secret not found.")
        await secret.fetch_all_links()
        if team is None:
            raise TeamNotFoundError("Team not found.")
        if chat is None:
            raise ChatNotFoundError("Chat not found.")
        if secret.submission is not None and not chat.is_attack:
            raise InvalidGuessError("Chat is not an attack chat.")
        if chat.is_evaluation != secret.is_evaluation:
            raise InvalidGuessError("Chat is not an evaluation chat.")

        async with secret_guessing_lock:
            existing_correct_guesses = await self.model.find_many(
                self.model.secret.id == secret.id,  # type: ignore
                Eq(self.model.is_correct, True),
            ).count()
            db_obj = models.SecretGuess(
                value=obj_in.value,
                secret=secret,
                guesser=team,
                chat=chat,
                guess_ranking=existing_correct_guesses + 1,
                is_evaluation=secret.is_evaluation,
                secret_evaluation_index=secret.evaluation_index,
                submission=secret.submission,
                is_correct=secret.value == obj_in.value,
            )
            await db_obj.create()
        return db_obj

    async def get_secret_guesses_per_guesser(
        self, *, secret_id: PydanticObjectId, guesser_id: PydanticObjectId
    ) -> list[models.SecretGuess]:
        guesses = await self.model.find_many(
            self.model.secret.id == secret_id,  # type: ignore
            self.model.guesser.id == guesser_id,  # type: ignore
        ).to_list()
        [await guess.fetch_all_links() for guess in guesses]
        return guesses

    async def get_n_secret_guesses_per_guesser(
        self, *, secret_id: PydanticObjectId, guesser_id: PydanticObjectId
    ) -> int:
        return await self.model.find_many(
            self.model.secret.id == secret_id,  # type: ignore
            self.model.guesser.id == guesser_id,  # type: ignore
        ).count()

    async def guesser_guessed_correctly_secret(self, secret_id: PydanticObjectId, guesser_id: PydanticObjectId) -> bool:
        correct_guess = await self.model.find_one(
            self.model.secret.id == secret_id,  # type: ignore
            self.model.guesser.id == guesser_id,  # type: ignore
            Eq(self.model.is_correct, True),
        )
        return correct_guess is not None

    async def get_most_recent_guess_per_guesser(
        self, guesser_id: PydanticObjectId, submission_id: PydanticObjectId, is_evaluation: bool = False
    ) -> models.SecretGuess | None:
        most_recent_guess_timestamp = (
            await self.model.find_many(
                self.model.guesser.id == guesser_id,  # type: ignore
                self.model.submission.id == submission_id,  # type: ignore
                Eq(self.model.is_evaluation, is_evaluation),
            )
            .project(TimeStampProjection)
            .max("timestamp")
        )
        if most_recent_guess_timestamp is None:
            return None
        guess = await self.model.find_one(
            self.model.guesser.id == guesser_id,  # type: ignore
            self.model.submission.id == submission_id,  # type: ignore
            Eq(self.model.is_evaluation, is_evaluation),
            self.model.timestamp == most_recent_guess_timestamp,
        )
        await guess.fetch_all_links()
        return guess

    async def get_correct_eval_guesses_per_submission(
        self, submission_id: PydanticObjectId
    ) -> list[models.SecretGuess]:
        guesses = await self.model.find_many(
            self.model.submission.id == submission_id,  # type: ignore
            Eq(self.model.is_correct, True),
            Eq(self.model.is_evaluation, True),
        ).to_list()
        [await guess.fetch_all_links() for guess in guesses]
        return guesses


secret_guess = CRUDSecretGuess(models.SecretGuess)
