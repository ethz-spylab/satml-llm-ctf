import datetime
from typing import Annotated

from beanie import Document, Indexed, Link

from .user import User


class APIKey(Document):
    key: Indexed(str, unique=True)  # type: ignore
    user: Annotated[Link[User], Indexed(unique=True)]
    created: datetime.datetime
    active: bool = True

    class Settings:
        name = "api_key"
