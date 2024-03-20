from beanie import Link, PydanticObjectId
from beanie.odm.operators.find.comparison import Eq
from beanie.odm.operators.find.logical import Or
from pydantic import BaseModel

from app import models, schemas
from app.config import ChatModel

from . import crud_secret, crud_secret_guess
from .base import CRUDBase
from .crud_user import user as crud_user


class UserNotInTeamError(Exception):
    pass


class DefenseProjection(BaseModel):
    defense: models.Defense


class CRUDDefense(CRUDBase[models.Defense, schemas.DefenseCreate, schemas.DefenseUpdate]):
    async def create(self, *, obj_in: schemas.DefenseCreate) -> models.Defense:
        user = await crud_user.get(id=obj_in.user_id)
        db_obj = models.Defense(
            defense_prompt=obj_in.defense_prompt, user=user, output_filters=obj_in.output_filters, name=obj_in.name
        )
        await db_obj.create()
        return db_obj

    @staticmethod
    async def submit(*, db_obj: models.Defense, user: models.User, model: ChatModel) -> models.DefenseSubmission:
        await db_obj.fetch_all_links()
        await user.fetch_all_links()
        if user.team is None:
            raise UserNotInTeamError()
        submission = models.DefenseSubmission(defense=db_obj, team=user.team, model=model)
        await submission.create()
        return submission

    @staticmethod
    async def get_submission_by_id(id: PydanticObjectId) -> models.DefenseSubmission | None:
        return await models.DefenseSubmission.get(id, fetch_links=True)

    @staticmethod
    async def get_multi_submissions(*, skip: int = 0, limit: int | None = 100) -> list[models.DefenseSubmission]:
        return (
            await models.DefenseSubmission.find_many(
                Or(Eq(models.DefenseSubmission.is_active, True), Eq(models.DefenseSubmission.is_active, None)),
                fetch_links=True,
            )
            .skip(skip)
            .limit(limit)
            .to_list()
        )

    @staticmethod
    async def deactivate_submission(*, id: PydanticObjectId) -> models.DefenseSubmission | None:
        submission = await models.DefenseSubmission.get(
            id,
            fetch_links=True,
        )
        if submission is None:
            return None
        submission.is_active = False
        await submission.save()
        return submission

    @staticmethod
    async def activate_submission(*, id: PydanticObjectId) -> models.DefenseSubmission | None:
        submission = await models.DefenseSubmission.get(
            id,
            fetch_links=True,
        )
        if submission is None:
            return None
        submission.is_active = True
        await submission.save()
        return submission

    @staticmethod
    async def get_submission_by_user_and_model(
        *, user: models.User, model: ChatModel
    ) -> models.DefenseSubmission | None:
        await user.fetch_all_links()
        if user.team is None:
            raise UserNotInTeamError()
        team: models.Team = user.team  # type: ignore
        return await models.DefenseSubmission.find_one(
            models.DefenseSubmission.team.id == team.id,  # type: ignore
            models.DefenseSubmission.model == model,
            fetch_links=True,
        )

    @staticmethod
    async def withdraw_submission(*, user: models.User, model: ChatModel) -> models.DefenseSubmission | None:
        current_submission = await defense.get_submission_by_user_and_model(user=user, model=model)
        if current_submission is not None:
            assert current_submission.id is not None
            secrets_to_remove = await crud_secret.secret.get_by_submission(submission_id=current_submission.id)
            for secret in secrets_to_remove:
                assert secret.id is not None
                await crud_secret_guess.secret_guess.remove_by_secret(secret_id=secret.id)
            await crud_secret.secret.remove_by_submission(submission_id=current_submission.id)
            await current_submission.delete()
        return current_submission

    @staticmethod
    async def get_submission_by_defense_and_model(defense_id: PydanticObjectId, model: ChatModel):
        return await models.DefenseSubmission.find_one(
            models.DefenseSubmission.defense.id == defense_id,
            models.DefenseSubmission.model == model,
            fetch_links=True,
        )

    async def get_by_user(self, *, user_id: PydanticObjectId, skip: int = 0, limit: int = 100) -> list[models.Defense]:
        return (
            await self.model.find_many(self.model.user.id == user_id, fetch_links=True)  # type: ignore
            .skip(skip)
            .limit(limit)
            .to_list()
        )

    async def get_by_team(self, *, user_id: PydanticObjectId, skip: int = 0, limit: int = 100) -> list[models.Defense]:
        user = await crud_user.get(id=user_id)
        if user is None:
            raise ValueError("User not found")
        await user.fetch_all_links()
        if user.team is None:
            raise ValueError("User is not in a team")

        defenses = []
        user.team.users = await Link.fetch_list(user.team.users, fetch_links=True)  # type: ignore
        for team_user in user.team.users:  # type: ignore
            defenses += await self.get_by_user(user_id=team_user.id, skip=skip, limit=limit)

        return defenses

    async def get_by_id_and_user(
        self, *, defense_id: PydanticObjectId, user_id: PydanticObjectId, team_id: PydanticObjectId | None = None
    ) -> models.Defense:
        db_obj = await self.get(defense_id)
        if db_obj is None:
            raise ValueError("Defense not found")
        await db_obj.fetch_all_links()
        if db_obj.user.id != user_id:  # type: ignore
            # Check if in team
            await db_obj.user.fetch_all_links()  # type: ignore
            if db_obj.user.team is None or team_id is None or db_obj.user.team.id != team_id:  # type: ignore
                raise ValueError("You are not the owner of this defense")
        return db_obj

    async def remove_by_user(self, *, defense_id: PydanticObjectId, user_id: PydanticObjectId) -> None:
        db_obj = await self.get(defense_id)
        if db_obj is None:
            raise ValueError("Defense not found")
        await db_obj.fetch_all_links()
        if db_obj is None:
            raise ValueError("Defense not found")
        if db_obj.user.id != user_id:  # type: ignore
            raise ValueError("You are not the owner of this defense")
        defense_submissions = models.DefenseSubmission.find(
            models.DefenseSubmission.defense.id == db_obj.id,
            fetch_links=True,
        )
        # Delete related documents
        await defense_submissions.delete()
        chats = models.Chat.find(
            models.Chat.defense.id == db_obj.id,
            fetch_links=True,
        )
        await chats.delete()
        await db_obj.delete()

    async def update_utility_evals(
        self,
        *,
        db_obj: models.Defense,
        request: schemas.UtilityEvalRequest,
        result: schemas.UtilityEvalResult,
        timestamp: str,
    ) -> models.Defense:
        """Update the list of utility evaluations of a defense."""
        db_obj.utility_evaluations.append(
            {
                "request": request,
                "result": result,
                "timestamp": timestamp,
            }
        )
        await db_obj.save()
        return db_obj

    async def get_utility_evals(self, *, db_obj: models.Defense) -> list[dict]:
        """Get the list of utility evaluations for a defense."""
        # TODO How to prevent utility requests with is_test=True from being seen? (Hope this is not a problem if we create a new defense for admin testing of a given participants' defense.)
        return db_obj.utility_evaluations

    @staticmethod
    async def get_submitted_defenses() -> list[models.Defense]:
        all_defenses = await models.DefenseSubmission.find_many(fetch_links=True).project(DefenseProjection).to_list()
        found_defense_ids = set()
        submitted_defenses = []
        for defense in all_defenses:
            if defense.defense.id not in found_defense_ids:
                found_defense_ids.add(defense.defense.id)
                submitted_defenses.append(defense.defense)
        return submitted_defenses


defense = CRUDDefense(models.Defense)
