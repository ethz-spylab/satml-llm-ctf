from pydantic import BaseModel

from app import enums


class LLMProviderAPIKeys(BaseModel):
    openai: str | None = None
    together: str | None = None

    def get_for_provider(self, provider: enums.APIProvider) -> str | None:
        match provider:
            case enums.APIProvider.openai:
                return self.openai
            case enums.APIProvider.together:
                return self.together
        raise ValueError("Provider key match failed")


class GenerateRequest(BaseModel):
    new_message: str
    api_keys: LLMProviderAPIKeys | None = None

    model_config = {
        "json_schema_extra": {"example": {"new_message": "Hi!", "api_keys": {"openai": None, "together": None}}}
    }
