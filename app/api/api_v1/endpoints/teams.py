import urllib.parse

from beanie import Link, PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from app import config, crud, models, schemas
from app.api import deps

router = APIRouter(
    dependencies=[Depends(deps.get_current_active_superuser_api_key)],
    include_in_schema=config.settings.hostname == "localhost",
)


async def _get_team_from_request(id: PydanticObjectId | None, name: str | None) -> models.Team:
    if id is not None:
        team = await crud.team.get(id)
    elif name is not None:
        team = await crud.team.get_by_name(name=name)
    else:
        raise HTTPException(status.HTTP_406_NOT_ACCEPTABLE, "Must provide team_id or team_name")
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    if id is not None and name is not None and (team.id != id or team.name != name):
        raise HTTPException(status.HTTP_406_NOT_ACCEPTABLE, "Team id and name do not match an existing team")
    return team


@router.post("/create", response_model=schemas.TeamCreationResponse)
async def create_team(name: str) -> schemas.TeamCreationResponse:
    name = urllib.parse.unquote_plus(name)
    try:
        team = await crud.team.create(obj_in=schemas.TeamCreate(name=name))
    except crud.CRUDError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    users = await Link.fetch_list(team.users, fetch_links=True)  # type: ignore
    return schemas.TeamCreationResponse(team_id=team.id, name=team.name, users=[u.email for u in users])  # type: ignore


@router.post("/delete", response_model=dict[str, str])
async def delete_team(id: PydanticObjectId | None = None, name: str | None = None) -> dict[str, str]:
    await _get_team_from_request(id, name)
    if id is not None:
        team = await crud.team.remove(id=id)  # type: ignore
    elif name is not None:
        team = await crud.team.remove_by_name(name=name)
    else:
        raise HTTPException(status.HTTP_406_NOT_ACCEPTABLE, "Must provide id or name")
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return {"detail": f"Team with id '{team.id}' and name '{team.name}' deleted"}


@router.post("/add-users", response_model=schemas.TeamCreationResponse)
async def add_users(creation_request: schemas.TeamEditUserRequest) -> schemas.TeamCreationResponse:
    team = await _get_team_from_request(creation_request.team_id, creation_request.team_name)
    assert team.id is not None
    # TODO: an error here could result in users updated but team not updated.
    # Probably need to keep the updated user objects and save at the end.
    for user_email in creation_request.users:
        user = await crud.user.get_by_email(email=user_email)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        if user.team is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "User already in a team")
        await crud.team.add_user(user=user, team=team)
    users = await Link.fetch_list(team.users, fetch_links=True)  # type: ignore
    return schemas.TeamCreationResponse(team_id=team.id, name=team.name, users=[u.email for u in users])  # type: ignore


@router.post("/remove-users", response_model=schemas.TeamCreationResponse)
async def remove_users(creation_request: schemas.TeamEditUserRequest) -> schemas.TeamCreationResponse:
    team = await _get_team_from_request(creation_request.team_id, creation_request.team_name)
    for user_email in creation_request.users:
        user = await crud.user.get_by_email(email=user_email)
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        if user.id not in [user.id for user in await Link.fetch_list(team.users, fetch_links=True)]:  # type: ignore
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not in team")
        await crud.team.remove_user(user=user, team=team)
    users = await Link.fetch_list(team.users, fetch_links=True)  # type: ignore
    return schemas.TeamCreationResponse(team_id=team.id, name=team.name, users=[u.email for u in users])  # type: ignore


@router.get("/", response_model=list[schemas.TeamInfo])
async def list_teams(
    team_name: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[schemas.TeamInfo]:
    if team_name is not None:
        return [await _get_team(None, team_name)]
    teams = await crud.team.get_multi(skip=skip, limit=limit)
    team_infos = []
    for team in teams:
        await team.fetch_all_links()
        team_users: list[models.User] = await Link.fetch_list(team.users, fetch_links=True)  # type: ignore
        users = [user.email for user in team_users]
        team_infos.append(schemas.TeamInfo(id=team.id, name=team.name, users=users))
    return team_infos


async def _get_team(id: PydanticObjectId | None, name: str | None):
    team = await _get_team_from_request(id, name)
    await team.fetch_all_links()
    team_users: list[models.User] = await Link.fetch_list(team.users, fetch_links=True)  # type: ignore
    users = [user.email for user in team_users]
    return schemas.TeamInfo(id=team.id, name=team.name, users=users)


@router.get("/{id}", response_model=schemas.TeamInfo)
async def get_team_by_id(id: PydanticObjectId) -> schemas.TeamInfo:
    return await _get_team(id, None)
