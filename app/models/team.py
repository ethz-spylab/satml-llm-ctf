from typing import TYPE_CHECKING

from beanie import Document, Indexed, Link

if TYPE_CHECKING:
    from .user import User


class Team(Document):
    name: Indexed(str, unique=True)  # type: ignore
    is_active: bool
    users: list["Link[User]"] = []

    class Settings:
        name = "team"
