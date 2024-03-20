import random

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from app import config, crud, models, schemas
from app.api import deps
from app.api.api_v1.endpoints.defense import idfy_user
from app.config import settings

router = APIRouter()


def idfy_submission(submission: models.DefenseSubmission) -> schemas.AttackerDefenseSubmissionInfo:
    return schemas.AttackerDefenseSubmissionInfo(
        id=submission.id,
        model=submission.model,
        team_name=submission.team.name,  # type: ignore
    )


async def get_submissions(skip=0, limit=100) -> list[schemas.AttackerDefenseSubmissionInfo]:
    submissions = await crud.defense.get_multi_submissions(skip=skip, limit=limit)
    return [idfy_submission(submission) for submission in submissions]


@router.get(
    "s",
    response_model=list[schemas.AttackerDefenseSubmissionInfo],
)
async def get_all_submissions(
    user: deps.ActiveUserAPIKeyDep, skip: int = 0, limit: int = 100
) -> list[schemas.AttackerDefenseSubmissionInfo]:
    """List submissions to attack. Submissions are shuffled in a different way for each team to prevent the same
    submissions to be attacked by everyone."""
    await user.fetch_all_links()
    if user.team is None:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You need to be part of a team to participate in the attack phase. Please sign up via the form on our website.",
        )
    submission_infos = await get_submissions(skip, limit)
    random.seed(int(str(user.team.id), 16))  # type: ignore
    random.shuffle(submission_infos)
    return submission_infos


@router.post(
    "/{submission_id}/deactivate",
    dependencies=[Depends(deps.get_current_active_superuser_api_key)],
    include_in_schema=settings.hostname == "localhost",
)
async def deactivate_submission(submission_id: PydanticObjectId) -> dict[str, str]:
    result = await crud.defense.deactivate_submission(id=submission_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    return {"info": "Submission deactivated successfully"}


@router.post(
    "/{submission_id}/activate",
    dependencies=[Depends(deps.get_current_active_superuser_api_key)],
    include_in_schema=settings.hostname == "localhost",
)
async def activate_submission(submission_id: PydanticObjectId) -> dict[str, str]:
    result = await crud.defense.activate_submission(id=submission_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    return {"info": "Submission activated successfully"}


@router.get(
    "/get_defenses",
    include_in_schema=config.settings.hostname == "localhost",
    response_model=list[schemas.OrganizerDefenseSubmissionInfo],
    dependencies=[Depends(deps.get_current_active_superuser_api_key)],
)
async def get_submissions_defenses(
    _: deps.ActiveSuperUserAPIKeyDep, skip: int = 0, limit: int = 100
) -> list[schemas.OrganizerDefenseSubmissionInfo]:
    submissions = await crud.defense.get_multi_submissions(skip=skip, limit=limit)
    return [
        schemas.OrganizerDefenseSubmissionInfo(
            id=s.id,
            team_name=s.team.name,  # type: ignore
            model=s.model,
            defense=idfy_user(s.defense),  # type: ignore
        )
        for s in submissions
    ]
