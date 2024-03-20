from typing import Any

from beanie import PydanticObjectId

from app import enums, models, schemas

from .base import CRUDBase
from .crud_team import team as crud_team
from .crud_user import user as crud_user


class CRUDTeamBudget(CRUDBase[models.TeamBudget, schemas.TeamBudgetCreate, schemas.TeamBudgetUpdate]):
    async def update(
        self, *, db_obj: models.TeamBudget, obj_in: schemas.TeamBudgetUpdate | dict[str, Any]
    ) -> models.TeamBudget:
        if isinstance(obj_in, dict):
            provider = obj_in["provider"]
            consumed = obj_in["consumed"]
        else:
            provider = obj_in.provider
            consumed = obj_in.consumed
        db_obj.provider_budgets[provider].consumed += consumed
        await db_obj.save()
        return db_obj

    async def get_by_user(self, *, user_id: PydanticObjectId) -> models.TeamBudget | None:
        # Get user team
        user = await crud_user.get(user_id)
        if user is None:
            raise ValueError("User not found")
        await user.fetch_all_links()
        if user is None:
            raise ValueError("Error retrieving your user, contact the organizers")
        team = user.team
        if team is None:
            return None
        # Return budget for team
        budget = await self.get_by_team(team_id=team.id)  # type: ignore
        return budget

    async def get_by_team(self, *, team_id: PydanticObjectId) -> models.TeamBudget | None:
        return await self.model.find_one(self.model.team.id == team_id, fetch_links=True)  # type: ignore

    async def create(self, *, obj_in: schemas.TeamBudgetCreate) -> models.TeamBudget:
        team = await crud_team.get(obj_in.team_id)
        db_obj = self.model(team=team, provider_budgets=obj_in.provider_budgets)
        await db_obj.create()
        return db_obj

    async def increase(self, *, obj_in: schemas.TeamBudgetCreate) -> models.TeamBudget:
        team = await crud_team.get(obj_in.team_id)
        if team is None:
            raise ValueError("Team not found")
        assert team.id is not None
        existing_budget = await self.get_by_team(team_id=team.id)
        if existing_budget is None:
            return await self.create(obj_in=obj_in)
        for provider, budget in obj_in.provider_budgets.items():
            existing_budget.provider_budgets[provider].limit += budget.limit
        await existing_budget.save()
        return existing_budget

    async def has_remaining_budget(self, *, user_id: PydanticObjectId, provider: enums.APIProvider) -> bool:
        u_budget = await self.get_by_user(user_id=user_id)
        if u_budget is None:
            return False
        provider_budget = u_budget.provider_budgets.get(provider, None)
        if provider_budget is None:
            return False
        return provider_budget.consumed < provider_budget.limit

    async def get_remaining_budget(self, *, user_id: PydanticObjectId, provider: enums.APIProvider) -> float:
        u_budget = await self.get_by_user(user_id=user_id)
        if u_budget is None:
            return 0.0
        provider_budget = u_budget.provider_budgets.get(provider, None)
        if provider_budget is None:
            return 0.0
        return provider_budget.limit - provider_budget.consumed

    async def consume_budget(
        self, *, user_id: PydanticObjectId, provider: enums.APIProvider, amount: float
    ) -> models.TeamBudget:
        u_budget = await self.get_by_user(user_id=user_id)
        if u_budget is None:
            raise ValueError("User doesn't have a budget")
        if not await self.has_remaining_budget(user_id=user_id, provider=provider):
            raise ValueError("User doesn't have remaining budget")
        return await self.update(db_obj=u_budget, obj_in=schemas.TeamBudgetUpdate(consumed=amount, provider=provider))


team_budget = CRUDTeamBudget(models.TeamBudget)
