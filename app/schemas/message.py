import datetime

from pydantic import BaseModel, Field

from app.enums import ChatRole, FilterType


class FilterStep(BaseModel):
    filter_type: FilterType | None
    content: str


class Message(BaseModel):
    role: ChatRole
    content: str
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    filter_steps: list[FilterStep] = Field(default_factory=list)


class AttackMessage(BaseModel):
    role: ChatRole
    content: str
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
