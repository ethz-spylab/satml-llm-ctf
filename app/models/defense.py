from typing import Annotated

from beanie import Document, Indexed, Link
from pymongo import IndexModel

from .. import config, schemas
from .team import Team
from .user import User


class Defense(Document):
    defense_prompt: str
    output_filters: schemas.OutputFilters
    user: Link[User]
    utility_evaluations: list[dict[str, schemas.UtilityEvalRequest | schemas.UtilityEvalResult | str]] = []
    name: str | None = None

    class Settings:
        name = "defense"


class DefenseSubmission(Document):
    defense: Annotated[Link[Defense], Indexed()]
    team: Annotated[Link[Team], Indexed()]
    model: config.ChatModel
    is_active: Annotated[bool, Indexed()] = True

    class Settings:
        name = "defense_submission"
        indexes = [
            IndexModel(
                ["model", "team"],
                unique=True,
                name="submission_model_team_unique_index",
            ),
            IndexModel(
                ["model", "defense"],
                unique=True,
                name="submission_model_defense_unique_index",
            ),
        ]
