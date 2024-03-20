from collections import defaultdict
from typing import Annotated

from beanie import Document, Indexed, Link

from app import enums, schemas

from .team import Team


class TeamBudget(Document):
    team: Annotated[Link[Team], Indexed(unique=True)]
    provider_budgets: dict[enums.APIProvider, schemas.ProviderBudget] = defaultdict(schemas.ProviderBudget)

    class Settings:
        name = "team_budget"
