from beanie import PydanticObjectId
from pydantic import BaseModel

from app import enums


class ProviderBudget(BaseModel):
    consumed: float = 0.0
    limit: float = 0.0


class TeamBudget(BaseModel):
    provider_budgets: dict[enums.APIProvider, ProviderBudget]


class TeamBudgetCreate(BaseModel):
    team_id: PydanticObjectId
    provider_budgets: dict[enums.APIProvider, ProviderBudget]


class TeamBudgetUpdate(BaseModel):
    provider: enums.APIProvider
    consumed: float = 0.0


class TeamBudgetCreationResponse(BaseModel):
    team_id: PydanticObjectId
    provider_budgets: dict[enums.APIProvider, ProviderBudget]
