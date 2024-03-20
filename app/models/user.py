from typing import TYPE_CHECKING, Optional

from beanie import Document, Indexed, Link

from app.enums import OAuth2SSOProvider

if TYPE_CHECKING:
    from .team import Team


class User(Document):
    openid_id: Indexed(str, unique=True)  # type: ignore
    email: Indexed(str, unique=True)  # type: ignore
    provider: OAuth2SSOProvider
    is_active: bool
    is_superuser: bool
    team: Optional["Link[Team]"] = None

    class Settings:
        name = "user"
