import datetime

from beanie import PydanticObjectId
from pydantic import BaseModel, Field


class APIKeyBase(BaseModel):
    key: str
    created: datetime.datetime


class APIKey(APIKeyBase):
    class Config:
        from_attributes = True


class APIKeyCreate(BaseModel):
    key: str
    user: PydanticObjectId
    created: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


class APIKeyUpdate(BaseModel):
    pass


class NewAPIKeyResponse(APIKey):
    pass
