import enum


class OAuth2SSOProvider(str, enum.Enum):
    google = "google"
    github = "github"


class ChatRole(str, enum.Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class FilterType(str, enum.Enum):
    llm = "llm"
    python = "python"


class APIProvider(str, enum.Enum):
    openai = "openai"
    together = "together"


class CompetitionPhase(str, enum.Enum):
    preparation = "preparation"
    defense = "defense"
    reconnaissance = "reconnaissance"
    evaluation = "evaluation"
    finished = "finished"
