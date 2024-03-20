import datetime
from typing import Annotated

from beanie import PydanticObjectId
from pydantic import BaseModel, Field, StringConstraints

from app.config import settings

ConstrainedSecretStr = Annotated[
    str,
    StringConstraints(
        min_length=settings.secret_length,
        max_length=settings.secret_length,
        pattern=rf"^[[a-zA-Z0-9]]{{{settings.secret_length}}}",
    ),
]


class Secret(BaseModel):
    value: ConstrainedSecretStr
    submission_id: PydanticObjectId | None = None
    is_evaluation: bool = False
    evaluation_index: int | None = None


class SecretCreate(BaseModel):
    value: ConstrainedSecretStr
    submission_id: PydanticObjectId | None
    is_evaluation: bool = False
    evaluation_index: int | None = None


class SecretUpdate(BaseModel):
    pass


class SecretGuess(BaseModel):
    secret_id: PydanticObjectId
    guesser_id: PydanticObjectId
    submission_id: PydanticObjectId
    chat_id: PydanticObjectId
    value: str
    is_correct: bool
    is_evaluation: bool
    guess_ranking: int
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class SecretGuessCreate(BaseModel):
    secret_id: PydanticObjectId
    guesser_id: PydanticObjectId
    chat_id: PydanticObjectId
    value: str


class SecretGuessUpdate(BaseModel):
    pass


class SecretGuessRequest(BaseModel):
    guess: ConstrainedSecretStr
    chat_id: PydanticObjectId


class SecretGuessResponse(BaseModel):
    correct: bool
    guesses_remaining: int
