from fastapi import APIRouter, HTTPException
from starlette import status

from app import config, crud, schemas
from app.api import deps

router = APIRouter()


@router.post("/create", include_in_schema=config.settings.hostname == "localhost")
async def create_budget(creation_request: schemas.TeamBudgetCreate, _: deps.ActiveSuperUserAPIKeyDep):
    budget = await crud.team_budget.create(
        obj_in=schemas.TeamBudgetCreate(
            team_id=creation_request.team_id, provider_budgets=creation_request.provider_budgets
        )
    )
    return schemas.TeamBudgetCreationResponse(team_id=budget.team.id, provider_budgets=budget.provider_budgets)  # type: ignore


@router.post("/increase", include_in_schema=False)
async def increase_budget(creation_request: schemas.TeamBudgetCreate, _: deps.ActiveSuperUserAPIKeyDep):
    budget = await crud.team_budget.increase(
        obj_in=schemas.TeamBudgetCreate(
            team_id=creation_request.team_id, provider_budgets=creation_request.provider_budgets
        )
    )
    return schemas.TeamBudgetCreationResponse(team_id=budget.team.id, provider_budgets=budget.provider_budgets)  # type: ignore


@router.get("/check")
async def check_budget(current_user: deps.ActiveUserAPIKeyDep) -> schemas.TeamBudget:
    assert current_user.id is not None
    budget = await crud.team_budget.get_by_user(user_id=current_user.id)
    if budget is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "You're not part of a team or your team doesn't have a budget. Fill the registration form to get one.",
        )
    return schemas.TeamBudget(provider_budgets=budget.provider_budgets)
