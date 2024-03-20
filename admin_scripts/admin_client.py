import urllib.parse

import requests
from beanie import PydanticObjectId
from pydantic import model_validator
from pydantic_settings import BaseSettings

from app import enums, schemas


class AdminClientSettings(BaseSettings):
    ctf_api_key: str = ""
    hostname: str = "localhost"
    port: int = 8008
    api_v1_str: str = "/api/v1"
    base_url: str = f"https://{hostname}" if hostname != "localhost" else f"http://{hostname}:{port}"
    api_url: str = f"{base_url}{api_v1_str}"

    @model_validator(mode="after")
    def _set_base_url(self) -> "AdminClientSettings":
        hostname = self.hostname
        port = self.port
        self.base_url = f"https://{hostname}" if hostname != "localhost" else f"http://{hostname}:{port}"
        self.api_url = f"{self.base_url}{self.api_v1_str}"
        return self


class AdminClient:
    def __init__(self, settings: AdminClientSettings = AdminClientSettings()):
        self.api_key = settings.ctf_api_key
        print("API key", self.api_key)
        self.api_url = settings.api_url
        self.headers = {"X-API-Key": self.api_key}
        self.json_headers = {
            "accept": "application/json",
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def get_users(self):
        url = f"{self.api_url}/users?limit=1000000"
        response = requests.get(url, headers=self.json_headers)
        response.raise_for_status()
        users = [schemas.UserInfo(**user) for user in response.json()]
        return users

    def get_teams(self) -> list[schemas.TeamInfo]:
        url = f"{self.api_url}/teams"
        response = requests.get(url, headers=self.json_headers)
        response.raise_for_status()
        teams = [schemas.TeamInfo(**team) for team in response.json()]
        return teams

    def create_team(self, name: str) -> schemas.TeamCreationResponse:
        url = f"{self.api_url}/teams/create"
        params = {"name": urllib.parse.quote_plus(name)}
        response = requests.post(url, params=params, headers=self.headers)
        response.raise_for_status()
        return schemas.TeamCreationResponse(**response.json())

    def add_users_to_team(
        self, users: list[str], team_name: str | None = None, team_id: PydanticObjectId | None = None
    ):
        url = f"{self.api_url}/teams/add-users"
        data = schemas.TeamEditUserRequest(users=users, team_name=team_name, team_id=team_id)
        response = requests.post(url, json=data.model_dump(), headers=self.json_headers)
        response.raise_for_status()

    def create_budget(self, team_id: PydanticObjectId, budget_per_provider: float):
        url = f"{self.api_url}/budget/create"
        provider_budgets = {
            provider: schemas.ProviderBudget(limit=budget_per_provider) for provider in enums.APIProvider
        }
        data = schemas.TeamBudgetCreate(team_id=team_id, provider_budgets=provider_budgets)
        response = requests.post(url, json=data.model_dump(), headers=self.json_headers)
        response.raise_for_status()

    def increase_budget(
        self, team_id: PydanticObjectId, provider_budgets: dict[enums.APIProvider, schemas.ProviderBudget]
    ):
        url = f"{self.api_url}/budget/increase"
        print(provider_budgets)
        data = schemas.TeamBudgetCreate(team_id=team_id, provider_budgets=provider_budgets)
        response = requests.post(url, json=data.model_dump(), headers=self.json_headers)
        response.raise_for_status()
        return schemas.TeamBudgetCreate(**response.json())

    def get_user_email(self, user_id: PydanticObjectId) -> str:
        url = f"{self.api_url}/users/{user_id}"
        response = requests.get(url, headers=self.json_headers)
        response.raise_for_status()
        user_info = schemas.UserInfo(**response.json())
        return user_info.email
