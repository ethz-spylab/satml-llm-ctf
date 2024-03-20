from typing import Annotated, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, EmailStr, StringConstraints, conlist, model_validator

from app.enums import OAuth2SSOProvider


# Shared properties
class UserBase(BaseModel):
    openid_id: str
    provider: OAuth2SSOProvider
    email: EmailStr | None = None
    team: Optional["Team"] = None
    is_active: bool | None = True
    is_superuser: bool = False


class UserInfo(BaseModel):
    id: PydanticObjectId
    openid_id: str
    provider: OAuth2SSOProvider
    email: EmailStr
    team: PydanticObjectId | None
    is_active: bool
    is_superuser: bool


# Properties to receive via API on creation
class UserCreate(UserBase):
    pass


# Properties to receive via API on update
class UserUpdate(UserBase):
    pass


class UserInDBBase(UserBase):
    id: PydanticObjectId | None = None

    class Config:
        from_attributes = True


# Additional properties to return via API
class User(UserInDBBase):
    pass


# Additional properties stored in DB
class UserInDB(UserInDBBase):
    pass


TeamName = Annotated[str, StringConstraints(min_length=1, max_length=16)]


class TeamBase(BaseModel):
    name: TeamName
    is_active: bool = True


# Properties to receive via API on creation
class TeamCreate(BaseModel):
    name: TeamName


# Properties to receive via API on update
class TeamUpdate(TeamBase):
    pass


class TeamInDBBase(TeamBase):
    id: PydanticObjectId
    users: list[User] = []

    class Config:
        from_attributes = True


class TeamCreationResponse(BaseModel):
    team_id: PydanticObjectId
    name: TeamName
    users: list[EmailStr] = []


class TeamEditUserRequest(BaseModel):
    team_id: PydanticObjectId | None = None
    team_name: TeamName | None = None
    users: conlist(EmailStr, min_length=1)  # type: ignore

    @model_validator(mode="after")
    def check_id_name(self) -> "TeamEditUserRequest":
        if self.team_id is None and self.team_name is None:
            raise ValueError("Must provide id or name")
        return self


# Additional properties to return via API
class Team(TeamInDBBase):
    pass


# Additional properties stored in DB
class TeamInDB(TeamInDBBase):
    pass


class TeamInfo(TeamBase):
    id: PydanticObjectId
    users: list[EmailStr] = []
