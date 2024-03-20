from typing import Annotated

import openai
from beanie import Link, PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from app import crud, enums, models, schemas, security
from app.api import deps
from app.config import settings
from app.crud.crud_secret import AllSecretsGuessedError
from app.internals import llm, output_filter

defense_router = APIRouter()
attack_router = APIRouter()


def _attack_fy_message(message: schemas.Message) -> schemas.AttackMessage:
    return schemas.AttackMessage(
        role=message.role,
        content=message.content,
        timestamp=message.timestamp,
    )


def _attack_fy_history(history: list[schemas.Message]) -> list[schemas.AttackMessage]:
    return [_attack_fy_message(message) for message in history]


async def are_guesses_exhausted(secret: models.Secret, guesser_id: PydanticObjectId) -> bool:
    assert secret.id is not None
    n_guesses_done = await crud.secret_guess.get_n_secret_guesses_per_guesser(
        secret_id=secret.id, guesser_id=guesser_id
    )
    return n_guesses_done >= settings.max_secret_guesses


@attack_router.get(
    "/most-recent-guess",
    response_model=PydanticObjectId | None,
    include_in_schema=settings.hostname == "localhost",
    dependencies=[Depends(deps.get_current_active_superuser_api_key)],
)
async def get_most_recent_guess_per_guesser(
    submission_id: PydanticObjectId, guesser_id: PydanticObjectId, is_evaluation: bool = False
) -> PydanticObjectId | None:
    most_recent_guess = await crud.secret_guess.get_most_recent_guess_per_guesser(
        guesser_id, submission_id, is_evaluation
    )
    return most_recent_guess.id if most_recent_guess is not None else None


async def get_secret_for_attack_chat(
    submission_id: PydanticObjectId, guesser_id: PydanticObjectId, is_evaluation: bool = False, new_secret: bool = False
) -> models.Secret:
    if is_evaluation and new_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create an evaluation chat while requesting a new secret. Secrets for evaluation chats"
            " are pre-generated.",
        )
    most_recent_guess = await crud.secret_guess.get_most_recent_guess_per_guesser(
        guesser_id, submission_id, is_evaluation
    )
    secret_create_obj = schemas.SecretCreate(
        value=security.generate_random_ascii_string(settings.secret_length), submission_id=submission_id
    )
    if (
        most_recent_guess is None
        or most_recent_guess.is_correct
        or await are_guesses_exhausted(most_recent_guess.secret, guesser_id)  # type: ignore
        or new_secret
    ):
        # No guess has been made for the current submission or the current secret has been guessed
        # correctly or the guesses have been exhausted: create new secret
        if is_evaluation:
            most_recent_guess_secret = most_recent_guess.secret if most_recent_guess is not None else None  # type: ignore
            try:
                return await crud.secret.get_new_evaluation_secret(
                    submission_id=submission_id,
                    most_recent_guess_secret=most_recent_guess_secret,  # type: ignore
                )
            except AllSecretsGuessedError:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="All secrets have been guessed and/or exhausted for this submission.",
                )
        return await crud.secret.create(obj_in=secret_create_obj)
    secret: models.Secret = most_recent_guess.secret  # type: ignore
    return secret


@attack_router.post("/create", response_model=schemas.AttackChatCreationResponse)
async def create_attack_chat(
    data: schemas.AttackChatCreate, current_user: deps.ActiveUserAPIKeyDep
) -> schemas.AttackChatCreationResponse:
    """
    Create a CHAT against an existing defense.

    In the body of the request, you must provide:
    - `defense_id`: the ID of a previous defense you created that will be loaded for the chat.
    - `evaluation`: a boolean to say whether this is a chat for the evaluation phase.
    - `new_secret` (optional): whether you want a new secret to be generated for the chat. Default is `false`.
    **This option is only available for non-evaluation chats**.

    See the schemas for details.

    If your request is successful, you will receive a `chat_id`, a `secret_id`, and the model for this submission.
    You can use the `chat_id` to interact with the chat through the generation endpoint.

    *Note that we do not allow deleting attack chats.* Contact the organizers if your chats contain sensitive
    information, and we'll proceed with deletion
    """
    submission = await crud.defense.get_submission_by_id(data.submission_id)
    if data.evaluation and data.new_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create an evaluation chat while requesting a new secret. Secrets for evaluation chats"
            " are pre-generated.",
        )
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    if not submission.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Submission is not active")
    if current_user.team is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create attack chats if you are in a team. Please fill in the form on our website.",
        )
    await current_user.fetch_all_links()
    if current_user.team.id == submission.team.id:  # type: ignore
        if not settings.hostname == "localhost":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This is your team's submission. You cannot create an attack chat against it.",
            )
    if data.evaluation and settings.comp_phase is not enums.CompetitionPhase.evaluation:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You cannot create an attack chat for evaluation yet."
        )
    user_team: models.Team = current_user.team  # type: ignore
    assert user_team.id is not None
    secret = await get_secret_for_attack_chat(data.submission_id, user_team.id, data.evaluation, data.new_secret)
    secret_id = secret.id
    model = submission.model
    defense_id = submission.defense.id  # type: ignore
    chat = await crud.chat.create(
        obj_in=schemas.ChatCreate(
            user_id=current_user.id,
            defense_id=defense_id,
            secret_id=secret_id,
            model=model,
            is_attack=True,
            is_evaluation=data.evaluation,
        )
    )
    return schemas.AttackChatCreationResponse(
        chat_id=chat.id, submission_id=data.submission_id, model=model, secret_id=secret_id
    )


@attack_router.get("/{id}", response_model=schemas.AttackChatResponse)
async def get_attack_chat(chat: deps.ChatDep) -> schemas.AttackChatResponse:
    """
    Retrieve a previous CHAT you created using its id.
    """
    await chat.fetch_all_links()
    submission = await crud.defense.get_submission_by_defense_and_model(chat.defense.id, chat.model)  # type: ignore
    attack_fied_history = _attack_fy_history(chat.history)
    return schemas.AttackChatResponse(
        model=chat.model,
        submission_id=submission.id,
        history=attack_fied_history,
        secret_id=chat.secret.id,  # type: ignore
    )


@attack_router.delete(
    "/{id}",
    response_model=schemas.ChatDeletionResponse,
    dependencies=[Depends(deps.get_current_active_superuser_api_key)],
    include_in_schema=settings.hostname == "localhost",
)
async def delete_attack_chat(chat: deps.ChatDep) -> schemas.ChatDeletionResponse:
    """
    Only available to admins!
    """
    return await delete_chat(chat)


@attack_router.get("/", response_model=list[PydanticObjectId])
async def get_user_attack_chats(
    user: deps.ActiveUserAPIKeyDep,
    skip: int = 0,
    limit: int = 100,
    evaluation: bool = False,
    submission_id: PydanticObjectId | None = None,
    show_by_team: bool = False,
) -> list[PydanticObjectId]:
    """
    Retrieve all your previous CHATS. There are the following optional parameters:
    - `evaluation`: if `true` then only the evaluation chats will be returned. Default is `false`.
    - `submission_id`: if provided, only the chats for the given submission will be returned.
    - `show_by_team`: if `true` then all the chats for the user's team will be returned. Default is `false`.
    """
    assert user.id is not None
    if show_by_team and user.team is not None:
        user_team = await Link.fetch_list(user.team.users, fetch_links=True)  # type: ignore
    else:
        user_team = [user]
    chats = []
    for user in user_team:
        assert user.id is not None
        chats += await crud.chat.get_by_user(
            user_id=user.id, skip=skip, limit=limit, attack=True, evaluation=evaluation
        )
    if submission_id is not None:
        chats = [chat for chat in chats if chat.secret.submission.id == submission_id]  # type: ignore
    return [chat.id for chat in chats]  # type: ignore


@attack_router.post("/{id}/new_message", response_model=schemas.AttackChatResponse)
async def generate_new_attack_message(
    data: schemas.GenerateRequest,
    chat: deps.ChatDep,
    current_user: Annotated[schemas.User, Depends(deps.rate_limit_user("10/minute"))],
) -> schemas.AttackChatResponse:
    """
    ⚠️ **This endpoint is rate limited to 10 requests per minute per user.**

    ⚠️ **This endpoint will consume credits from your API keys or Team Budget.**

    ⚠️ **You should wait for the request to return before sending a new request for the same `id`. Otherwise, we cannot guarantee that your requests will succeed, or that the chat history on the server will be consistent with what you intended.**

    Generate a new message in a CHAT. Allows you to have a conversation with a model and a defense. This endpoint is equivalent to the chat mechanism in our [interface](https://ctf.spylab.ai/defense).

    In the request URL, you must provide:
    - `id`: the ID of the chat you want to interact with.

    In the body of the request, you must provide:
    - `new_message`: the text message you want to send to the model.
    - `api_keys` (optional): you own API keys for OAI and/or Together AI. If you don't provide any, budget from your Team will be used.
    """
    new_chat = await generate_new_message(data, chat, current_user)
    submission = await crud.defense.get_submission_by_defense_and_model(new_chat.defense_id, chat.model)
    attack_fied_history = _attack_fy_history(new_chat.history)
    return schemas.AttackChatResponse(
        model=new_chat.model, submission_id=submission.id, history=attack_fied_history, secret_id=new_chat.secret_id
    )


@defense_router.post("/create-with-existing-defense", response_model=schemas.ChatCreationResponse)
async def create_chat_with_existing_defense(
    data: schemas.ExistingDefenseChatCreate, current_user: deps.ActiveUserAPIKeyDep
) -> schemas.ChatCreationResponse:
    """
    Create a CHAT against an existing defense.

    In the body of the request, you must provide:
    - `secret`: the secret to use for the chat. Remember in the next phase, the secrets will be randomly generated!
    - `defense_id`: the ID of a previous defense you created that will be loaded for the chat.
    - `model`: the model to use for the chat. You can choose between GPT-3.5 and LLaMA-2-70B Chat.

    See the schemas for details.

    If your request is successful, you will receive a `chat_id` and a `defense_id`. You can use the `chat_id` to interact with the chat through the generation endpoint, and the `defense_id` for submission or creating new chats.
    """
    secret_value = (
        data.secret if data.secret is not None else security.generate_random_ascii_string(settings.secret_length)
    )
    secret = await crud.secret.create(obj_in=schemas.SecretCreate(value=secret_value, submission_id=None))
    chat = await crud.chat.create(
        obj_in=schemas.ChatCreate(
            user_id=current_user.id, defense_id=data.defense_id, secret_id=secret.id, model=data.model
        )
    )
    return schemas.ChatCreationResponse(chat_id=chat.id, defense_id=data.defense_id)


@defense_router.post("/create-with-new-defense", response_model=schemas.ChatCreationResponse)
async def create_chat_with_new_defense(
    data: schemas.NewDefenseChatCreate, current_user: deps.ActiveUserAPIKeyDep
) -> schemas.ChatCreationResponse:
    """
    Create a DEFENSE and a CHAT to interact with it.

    In the body of the request, you must provide:
    - `secret`: the secret to use for the chat. Remember in the next phase, the secrets will be randomly generated!
    - `defense`: define the new defense you want to create. Check the schema for details.
    - `model`: the model to use for the chat. You can choose between GPT-3.5 and LLaMA-2-70B Chat.

    In case you want to load an already existing defense, you can set the `defense` parameter to `null` and provide the `defense_id` instead.

    See the schemas for details.

    If your request is successful, you will receive a `chat_id` and a `defense_id`. You can use the `chat_id` to interact with the chat through the generation endpoint, and the `defense_id` for submission or creating new chats.
    """

    # Ensure there is at most 1 filter of each possible type in data.defense.output_filters
    filter_types = [filter.type for filter in data.defense.output_filters]
    if len(filter_types) != len(set(filter_types)):
        raise ValueError("There can be at most one filter of each type")

    defense_create = schemas.DefenseCreate(
        defense_prompt=data.defense.defense_prompt,
        output_filters=data.defense.output_filters,
        user_id=current_user.id,
        name=data.defense.name,
    )
    defense = await crud.defense.create(obj_in=defense_create)
    return await create_chat_with_existing_defense(
        schemas.ExistingDefenseChatCreate(model=data.model, defense_id=defense.id, secret=data.secret), current_user
    )


@defense_router.get("/{id}", response_model=schemas.ChatResponse)
async def get_chat(chat: deps.ChatDep) -> schemas.ChatResponse:
    """
    Retrieve a previous CHAT you created using its id.
    """
    return schemas.ChatResponse(model=chat.model, defense_id=chat.defense.id, history=chat.history)  # type: ignore


@defense_router.post("/{id}/delete", response_model=schemas.ChatDeletionResponse)
async def delete_chat(chat: deps.ChatDep) -> schemas.ChatDeletionResponse:
    assert chat.id is not None
    await crud.chat.remove(id=chat.id)
    return schemas.ChatDeletionResponse(chat_id=chat.id)


@defense_router.get("s", response_model=list[PydanticObjectId])
async def get_user_chats(user: deps.ActiveUserAPIKeyDep, skip: int = 0, limit: int = 100) -> list[PydanticObjectId]:
    """
    Retrieve all your previous CHATS.
    """
    assert user.id is not None
    chats = await crud.chat.get_by_user(user_id=user.id, skip=skip, limit=limit)
    return list(map(lambda chat: chat.id, chats))  # type: ignore


@defense_router.post("/{id}/new_message", response_model=schemas.ChatResponse)
async def generate_new_message(
    data: schemas.GenerateRequest,
    chat: deps.ChatDep,
    current_user: Annotated[schemas.User, Depends(deps.rate_limit_user("10/minute"))],
) -> schemas.ChatResponse:
    """
    ⚠️ **This endpoint is rate limited to 10 requests per minute per user.**

    ⚠️ **This endpoint will consume credits from your API keys or Team Budget.**

    ⚠️ **You should wait for the request to return before sending a new request for the same `id`. Otherwise, we cannot guarantee that your requests will succeed, or that the chat history on the server will be consistent with what you intended.**

    Generate a new message in a CHAT. Allows you to have a conversation with a model and a defense. This endpoint is equivalent to the chat mechanism in our [interface](https://ctf.spylab.ai/defense).

    In the request URL, you must provide:
    - `id`: the ID of the chat you want to interact with.

    In the body of the request, you must provide:
    - `new_message`: the text message you want to send to the model.
    - `api_keys` (optional): you own API keys for OAI and/or Together AI. If you don't provide any, budget from your Team will be used.
    """
    new_user_message = schemas.Message(role=enums.ChatRole.user, content=data.new_message)
    updated_chat = await crud.chat.append(db_obj=chat, obj_in=schemas.ChatUpdate(message=new_user_message), save=False)
    provider = llm.get_model_provider(chat.model.value)
    if data.api_keys is None or data.api_keys.get_for_provider(provider) is None:
        remaining_budget = await crud.team_budget.get_remaining_budget(user_id=current_user.id, provider=provider)
        # TODO: maybe estimate the cost of the incoming message
        if remaining_budget <= 0.0:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient budget, please provide your own API key.",
            )
        user_provided_key = False
        llm_provider_api_key = settings.get_api_key_for_provider(provider)
    else:
        llm_provider_api_key = data.api_keys.get_for_provider(provider)  # type: ignore
        user_provided_key = True
    try:
        model_output, generation_cost = await llm.generate_chat(
            settings.system_prompt,
            settings.secret_prompt,
            updated_chat,
            llm_provider_api_key,
        )
    except openai.OpenAIError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"OpenAI API error: {e}. If you have a team budget,"
                f"note that your team budget has NOT been consumed.",
            ),
        )

    # Update user budget with cost if using our API key
    if user_provided_key is False:
        await crud.team_budget.consume_budget(user_id=current_user.id, provider=provider, amount=generation_cost)

    # Check if defense has llm filter to check budget
    uses_llm_filter = False
    for filter in chat.defense.output_filters:  # type: ignore
        if filter.type == enums.FilterType.llm:
            uses_llm_filter = True
            break

    if uses_llm_filter and not user_provided_key:
        remaining_budget = await crud.team_budget.get_remaining_budget(user_id=current_user.id, provider=provider)
        # TODO: maybe estimate the cost of the incoming message
        if remaining_budget <= 0.0:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient budget, please provide your own API key.",
            )
    try:
        filter_steps, filter_cost = await output_filter.apply_output_filters(
            [msg.content for msg in chat.history],
            model_output,
            chat.secret.value,  # type: ignore
            chat.defense.output_filters,  # type: ignore
            chat.model.value,
            llm_provider_api_key,
        )
    except openai.OpenAIError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OpenAI API error: {e}. Note that your budget has NOT been consumed.",
        )

    # Update user budget with cost if using our API key
    if uses_llm_filter and not user_provided_key:
        await crud.team_budget.consume_budget(user_id=current_user.id, provider=provider, amount=filter_cost)

    new_message = schemas.Message(
        role=enums.ChatRole.assistant, content=filter_steps[-1].content, filter_steps=filter_steps
    )

    updated_chat = await crud.chat.append(
        db_obj=updated_chat, obj_in=schemas.ChatUpdate(message=new_message), save=True
    )

    return schemas.ChatResponse(
        model=updated_chat.model,
        defense_id=updated_chat.defense.id,  # type: ignore
        history=updated_chat.history,  # type: ignore
        secret_id=updated_chat.secret.id,  # type: ignore
    )
