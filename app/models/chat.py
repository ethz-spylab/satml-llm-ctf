from typing import TYPE_CHECKING

from beanie import Document, Link

from app import schemas
from app.config import ChatModel

from .defense import Defense
from .user import User

if TYPE_CHECKING:
    from .secret import Secret


class Chat(Document):
    user: Link[User]
    secret: Link["Secret"]
    model: ChatModel
    defense: Link[Defense]
    history: list[schemas.Message] = []
    is_attack: bool = False
    is_evaluation: bool = False

    class Settings:
        name: str = "chat"
