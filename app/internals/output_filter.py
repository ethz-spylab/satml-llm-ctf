from app import enums, schemas

from .code_exec import execute_function
from .llm import filter_with_llm


async def execute_filter(
    output_filter: schemas.OutputFilter,
    chat_history: list[str],
    model_output: str,
    secret: str,
    model: str,
    llm_provider_api_key: str | None,
) -> tuple[str, float]:
    match output_filter.type:
        case enums.FilterType.llm:
            assert llm_provider_api_key is not None
            return await filter_with_llm(
                output_filter.code_or_prompt,
                chat_history,
                model_output,
                secret,
                model,
                llm_provider_api_key,
            )
        case enums.FilterType.python:
            return execute_function(
                output_filter.code_or_prompt, chat_history, model_output, secret
            ), 0.0  # COST=0 for non-model filters
        case _:
            raise NotImplementedError()


async def apply_output_filters(
    chat_history: list[str],
    model_output: str,
    secret: str,
    output_filters: schemas.OutputFilters,
    model: str,
    llm_provider_api_key: str | None,
) -> tuple[list[schemas.FilterStep], float]:
    filtered_output = model_output
    cost = 0.0
    steps = [schemas.FilterStep(content=filtered_output, filter_type=None)]

    for output_filter in output_filters:
        filtered_output, cost_step = await execute_filter(
            output_filter, chat_history, filtered_output, secret, model, llm_provider_api_key
        )
        steps.append(schemas.FilterStep(filter_type=output_filter.type, content=filtered_output))

        cost += cost_step

    return steps, cost
