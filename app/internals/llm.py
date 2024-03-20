import litellm

from app import enums, schemas
from app.config import settings

ConversationContent = list[tuple[str | None, str | None]]

TOGETHER_PREFIX = "together_ai/togethercomputer"

ROLE_MAPPING = {
    enums.ChatRole.user: "user",
    enums.ChatRole.assistant: "assistant",
    enums.ChatRole.system: "system",
}


def is_openai(model: str) -> bool:
    return model.startswith("openai/")


def is_together(model: str) -> bool:
    return model.startswith("meta/")


def get_model_provider(model: str) -> enums.APIProvider:
    if is_openai(model):
        return enums.APIProvider.openai
    elif is_together(model):
        return enums.APIProvider.together
    raise ValueError(f"Invalid model: {model}")


def parse_openai_model(model: str) -> str:
    return model.split("/")[1]


def parse_together_model(model: str) -> str:
    return f"{TOGETHER_PREFIX}/{model.split('/')[1]}"


MODEL_PARSERS = {enums.APIProvider.openai: parse_openai_model, enums.APIProvider.together: parse_together_model}


def parse_model_to_litellm(model: str) -> str:
    provider = get_model_provider(model)
    return MODEL_PARSERS[provider](model)


def build_openai_conversation(system_prompt: str, conversation: list[schemas.Message]) -> list[dict[str, str]]:
    conversation_list = []

    if len(system_prompt):
        conversation_list.append({"role": ROLE_MAPPING[enums.ChatRole.system], "content": system_prompt})

    for message in conversation:
        role = ROLE_MAPPING[message.role]
        conversation_list.append({"role": role, "content": message.content})
    return conversation_list


def build_system_prompt(system_prompt: str, secret_prompt: str, secret: str, defense_prompt: str) -> str:
    return f"{system_prompt} {secret_prompt.format(secret=secret)} {defense_prompt}"


async def generate(llm_provider_api_key, messages, model):
    completion = await litellm.acompletion(
        model=parse_model_to_litellm(model),
        messages=messages,
        max_tokens=settings.max_tokens,
        api_key=llm_provider_api_key,
        request_timeout=settings.llm_request_timeout,
    )
    output = completion.choices[0].message.content  # type: ignore
    cost = litellm.completion_cost(completion_response=completion)
    return output, cost


async def generate_chat(
    system_prompt: str,
    secret_prompt: str,
    chat: schemas.Chat,
    llm_provider_api_key: str,
) -> tuple[str, float]:
    system_prompt = build_system_prompt(system_prompt, secret_prompt, chat.secret.value, chat.defense.defense_prompt)
    messages = build_openai_conversation(system_prompt, chat.history)
    return await generate(llm_provider_api_key, messages, chat.model.value)


async def filter_with_llm(
    prompt: str,
    chat_history: list[str],
    model_output: str,
    secret: str,
    model: str,
    llm_provider_api_key: str,
) -> tuple[str, float]:
    prompt = prompt.format(last_user_prompt=chat_history[-1], secret=secret, model_output=model_output)
    history = [schemas.Message(role=enums.ChatRole.user, content=prompt)]
    messages = build_openai_conversation(
        "", history
    )  # JAVI:  This removes system prompt. Recommended by LLaMA and works on OAI.
    filtered_output, cost = await generate(llm_provider_api_key, messages, model)
    return filtered_output, cost
