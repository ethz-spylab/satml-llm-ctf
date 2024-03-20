from typing import Annotated

from pydantic import BaseModel, Field


class AttackerScore(BaseModel):
    name: str
    points: int


class SubmissionScore(BaseModel):
    name: str
    value: Annotated[float, Field(strict=True, ge=0, le=1)]
    attackers: list[AttackerScore]
