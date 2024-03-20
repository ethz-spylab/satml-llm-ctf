import datetime
from typing import Annotated

import pymongo
from beanie import Document, Indexed, Link
from pydantic import Field
from pymongo import IndexModel

from .chat import Chat
from .defense import DefenseSubmission
from .team import Team


class Secret(Document):
    value: str
    submission: Annotated[Link[DefenseSubmission] | None, Indexed()]
    is_evaluation: Annotated[bool, Indexed()] = False
    evaluation_index: Annotated[int | None, Indexed()] = None

    class Settings:
        name = "secret"
        indexes = [
            IndexModel(["submission", "evaluation_index"], name="submission_evaluation_index_index"),
        ]


class SecretGuess(Document):
    secret: Link[Secret]
    value: str
    guesser: Link[Team]
    chat: Link[Chat]
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    is_evaluation: bool = False
    is_correct: bool = False
    submission: Link[DefenseSubmission] = None  # type: ignore
    secret_evaluation_index: int | None = None
    guess_ranking: int = 1

    class Settings:
        name = "secret_guess"
        max_nesting_depth = 1
        indexes = [
            IndexModel(
                ["secret", "guesser"],
                name="secret_guesser_index",
            ),
            IndexModel(["guesser", "submission"], name="guesser_submission"),
            IndexModel(["guesser", "submission", "is_evaluation"], name="guesser_submission_is_evaluation_index"),
            IndexModel(
                ["guesser", "submission", "is_evaluation", ("timestamp", pymongo.DESCENDING)],
                name="guesser_submission_is_evaluation_timestamp_index",
            ),
            IndexModel(
                ["secret", "guesser", "is_correct"],
                name="secret_guesser_is_correct_index",
            ),
            IndexModel(
                ["secret", "guesser", ("timestamp", pymongo.DESCENDING), "is_evaluation"],
                name="secret_guesser_timestamp_is_evaluation_unique_index",
                unique=True,
            ),
            IndexModel(
                ["secret", "guesser", "is_correct", "is_evaluation"],
                name="secret_guesser_is_correct_is_evaluation_index",
            ),
            IndexModel(
                ["secret", "is_correct", "is_evaluation"],
                name="secret_is_correct_is_evaluation_index",
            ),
            IndexModel(
                ["is_evaluation", "guess_ranking"],
                name="is_evaluation_guess_ranking_index",
            ),
        ]
