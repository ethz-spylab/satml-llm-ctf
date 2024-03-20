from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from app import crud, models, schemas, security
from app.api import deps
from app.config import settings

router = APIRouter()


@router.post("/{secret_id}/guess", response_model=schemas.SecretGuessResponse)
async def guess_secret(
    secret_id: PydanticObjectId, data: schemas.SecretGuessRequest, current_user: deps.ActiveUserAPIKeyDep
) -> schemas.SecretGuessResponse:
    """
    Get whether your secret guess is correct. As part of the URL, you need to provide:
    - `secret_id`: the ID of the secret you're trying to guess.

    As part of the request body, you need to provide:
        - `guess`: your guess for the secret.
        - `chat_id`: the ID of the chat that lead you to the guess.

    As a response, you will get a response containing whether your guess was correct and how many guesses you have left
    for this secret.
    """
    if current_user.team is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only guess secrets if you are in a team. Please fill in the form on our website.",
        )
    secret = await crud.secret.get(id=secret_id)
    if secret is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Secret with the given ID not found.",
        )
    await secret.fetch_link("submission")
    await current_user.fetch_link("team")
    if secret.submission.id == current_user.team.id:  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot guess a secret related to your own submission.",
        )
    await secret.fetch_all_links()
    await current_user.fetch_all_links()
    await secret.submission.fetch_all_links()  # type: ignore
    has_guessed_correctly = await crud.secret_guess.guesser_guessed_correctly_secret(
        secret_id=secret_id,
        guesser_id=current_user.team.id,  # type: ignore
    )
    if has_guessed_correctly:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have already guessed this secret correctly.",
        )
    guesses_remaining_dict = await get_remaining_guesses(secret_id=secret_id, current_user=current_user)
    guesses_remaining = guesses_remaining_dict["guesses_remaining"]
    if guesses_remaining <= 0:
        if secret.is_evaluation:
            error_message = "You must move onto another submission."
        else:
            error_message = "Start a new chat with this submission to get a new secret."
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You have no guesses left for this secret. {error_message}",
        )
    correct = secret.value == data.guess
    team: models.Team = current_user.team  # type: ignore
    try:
        await crud.secret_guess.create(
            obj_in=schemas.SecretGuessCreate(
                secret_id=secret_id, guesser_id=team.id, value=data.guess, chat_id=data.chat_id
            )
        )
    except crud.CRUDError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    return schemas.SecretGuessResponse(correct=correct, guesses_remaining=guesses_remaining - 1)


@router.get("/{secret_id}/guesses", response_model=list[schemas.SecretGuess])
async def get_secret_guesses(
    secret_id: PydanticObjectId, current_user: deps.ActiveUserAPIKeyDep
) -> list[schemas.SecretGuess]:
    """
    Get all the guesses for a given secret.  As part of the URL, you need to provide:
    - `secret_id`: the ID of the secret you're trying to guess.

    As a response, you will get a JSON list with the following information for each element:
    - `secret_id`: the ID of the secret you are guessing
    - `guesser_id`: the ID of your team
    - `submission_id`: the ID of the submission you are attacking
    - `chat_id`: the chat with which you guessed the secret
    - `timestamp`: the timestamp of the guess
    - `value`: the value of your guess
    - `is_correct`: whether the guess is correct
    - `is_evaluation`: whether it is an evaluation guess
    - `guess_ranking`: the rank of your guess (if correct) compared to otherx users (only relevant for the evaluation phase)
    """
    if current_user.team is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only guess secrets if you are in a team. Please fill in the form on our website.",
        )
    await current_user.fetch_link("team")
    team: models.Team = current_user.team  # type: ignore
    assert team.id is not None
    guesses = await crud.secret_guess.get_secret_guesses_per_guesser(secret_id=secret_id, guesser_id=team.id)
    return [
        schemas.SecretGuess(
            secret_id=guess.secret.id,  # type: ignore
            guesser_id=guess.guesser.id,  # type: ignore
            submission_id=guess.submission.id,  # type: ignore
            chat_id=guess.chat.id,  # type: ignore
            timestamp=guess.timestamp,
            value=guess.value,
            is_correct=guess.is_correct,
            is_evaluation=guess.is_evaluation,
            guess_ranking=guess.guess_ranking,
        )
        for guess in guesses
    ]


@router.get("/{secret_id}/remaining_guesses", response_model=dict[str, int])
async def get_remaining_guesses(secret_id: PydanticObjectId, current_user: deps.ActiveUserAPIKeyDep) -> dict[str, int]:
    """
    Get how many guesses are left for a given secret.  As part of the URL, you need to provide:
    - `secret_id`: the ID of the secret you're trying to guess.

    As a result, you will get a JSON in the form `{"guesses_remaining": guesses_remaining}`.
    """
    if current_user.team is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only guess secrets if you are in a team. Please fill in the form on our website.",
        )
    await current_user.fetch_link("team")
    team: models.Team = current_user.team  # type: ignore
    assert team.id is not None
    tot_guesses = await crud.secret_guess.get_n_secret_guesses_per_guesser(secret_id=secret_id, guesser_id=team.id)
    guesses_remaining = settings.max_secret_guesses - tot_guesses
    return {"guesses_remaining": guesses_remaining}


@router.post(
    "/create-evaluation-secrets",
    response_model=list[schemas.Secret],
    dependencies=[Depends(deps.get_current_active_superuser_api_key)],
    include_in_schema=settings.hostname == "localhost",
)
async def create_evaluation_secrets() -> list[schemas.Secret]:
    existing_secrets = await crud.secret.get_evaluation_secrets()
    if len(existing_secrets) > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Evaluation secrets already exist.",
        )
    all_submissions = await crud.defense.get_multi_submissions()
    all_secrets = []
    for submission in all_submissions:
        for i in range(settings.eval_secrets_per_submission):
            secret_value = security.generate_random_ascii_string(length=settings.secret_length)
            secret = await crud.secret.create(
                obj_in=schemas.SecretCreate(
                    value=secret_value, submission_id=submission.id, is_evaluation=True, evaluation_index=i
                )
            )
            assert secret.submission is not None
            all_secrets.append(
                schemas.Secret(
                    value=secret.value,
                    submission_id=secret.submission.id,  # type: ignore
                    is_evaluation=True,
                    evaluation_index=i,
                )
            )
    return all_secrets


@router.delete(
    "/remove-evaluation-secrets",
    response_model=dict[str, str],
    dependencies=[Depends(deps.get_current_active_superuser_api_key)],
    include_in_schema=settings.hostname == "localhost",
)
async def remove_evaluation_secrets(confirmation: str) -> dict[str, str]:
    if confirmation != "CONFIRM_REMOVE_EVALUATION_SECRETS":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please confirm the action by typing the correct phrase.",
        )
    existing_secrets = await crud.secret.get_evaluation_secrets()
    for secret in existing_secrets:
        await crud.secret.remove(id=secret.id)
    return {"detail": "Evaluation secrets removed."}
