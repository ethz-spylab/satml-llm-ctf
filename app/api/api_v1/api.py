from fastapi import APIRouter, Depends

from app import config
from app.api import deps
from app.api.api_v1.endpoints import budget, chat, defense, key, models, scores, secret, submission, teams, users
from app.enums import CompetitionPhase

api_router = APIRouter()
api_router.include_router(
    chat.defense_router,
    prefix="/chat/defense",
    tags=["chat/defense"],
    dependencies=[Depends(deps.get_api_key_user_dependency_for_current_phase(CompetitionPhase.defense))],
    include_in_schema=config.settings.comp_phase is CompetitionPhase.defense or config.settings.hostname == "localhost",
)
api_router.include_router(
    chat.attack_router,
    prefix="/chat/attack",
    tags=["chat/attack"],
    dependencies=[
        Depends(
            deps.get_api_key_user_dependency_for_current_phase(
                CompetitionPhase.reconnaissance, CompetitionPhase.evaluation
            )
        )
    ],
    include_in_schema=config.settings.comp_phase in {CompetitionPhase.reconnaissance, CompetitionPhase.evaluation}
    or config.settings.hostname == "localhost",
)
api_router.include_router(models.router, tags=["models"])
api_router.include_router(
    defense.router,
    prefix="/defense",
    tags=["defense"],
    dependencies=[Depends(deps.get_api_key_user_dependency_for_current_phase(CompetitionPhase.defense))],
    include_in_schema=config.settings.comp_phase is CompetitionPhase.defense or config.settings.hostname == "localhost",
)
api_router.include_router(
    users.router, prefix="/users", tags=["users"], include_in_schema=config.settings.hostname == "localhost"
)
api_router.include_router(
    key.router, prefix="/key", tags=["key"], include_in_schema=config.settings.hostname == "localhost"
)
api_router.include_router(scores.router, prefix="/scores", tags=["scores"])
api_router.include_router(budget.router, prefix="/budget", tags=["budget"])
api_router.include_router(
    secret.router,
    prefix="/secret",
    tags=["secret"],
    dependencies=[
        Depends(
            deps.get_api_key_user_dependency_for_current_phase(
                CompetitionPhase.reconnaissance, CompetitionPhase.evaluation
            )
        )
    ],
    include_in_schema=config.settings.comp_phase in {CompetitionPhase.reconnaissance, CompetitionPhase.evaluation}
    or config.settings.hostname == "localhost",
)
api_router.include_router(submission.router, prefix="/submission", tags=["submission"])
api_router.include_router(teams.router, prefix="/teams", tags=["team"])
