# %%
"""
We check whether the model can pass some benchmarks.
"""
# Some code is from https://github.com/hendrycks/test/blob/master/evaluate.py

import asyncio
import random
import re
from pathlib import Path

import pandas as pd

from app import models, schemas, security
from app.api import api_v1, deps


def format_subject(subject: str):
    l = subject.split("_")
    s = ""
    for entry in l:
        s += " " + entry
    return s.strip()


prompt_final_answer = """\
Answer so that the very last character of your response is A, B, C, or D, preceded by [Final answer] and a space. \
For example, if through your reasoning you conclude that the answer is C, end your response with [Final answer] C. \
\n"""

prompt_repeat = """\
Figure out the answer to the question and respond with [Final answer] followed by the answer. \
"""

prompt_repeat_one_letter = """\
Say "Answer: " followed by the letter of the answer. \
"""

prompt_multiturn_start = """\
The answers (A, B, C, D) will be given in multiple turns. After all the turns, you will be asked to give the final answer.
Until then, just think about the question and the answers. \
"""


def gen_prompt(subject: str):
    if subject.startswith("arb"):
        prompt = (
            "The following is a multiple choice bar exam question. "
            + "You are an expert test taker. Read the question carefully, reason about it, and answer it.\nQuestion:"
        )

    else:
        prompt = (
            f"The following is a multiple choice question (with answers) about {format_subject(subject)}. "
            + "You are an expert test taker. Read the question carefully, reason about it, and answer it.\nQuestion:"
        )

    return prompt


def format_question_singleturn(question: str, choices: list, subject: str):
    prompt = gen_prompt(subject)
    prompt += question + "\n"
    for i in range(len(choices)):
        prompt += f"{chr(ord('A') + i)}. {choices[i]}\n"
    prompt += "\n"
    prompt += "In your solution, think step by step and deduce the final answer."
    return prompt


def format_question_multiturn(question: str, subject: str):
    prompt = gen_prompt(subject)
    prompt += question + "\n"
    prompt += prompt_multiturn_start
    return prompt


def is_correct(output, correct_answer) -> bool:
    # This function should be implemented based on the criteria for a correct response
    # Get the last appearance of a lone character A, B, C or D in the output; compare it to the answer
    # Return True if the response is correct, False otherwise

    assert correct_answer in ["A", "B", "C", "D"]
    try:
        # find "Answer: " followed by a letter A, B, C or D
        pred = re.findall(r"Answer: ([A-D])", output)[-1]
    except IndexError:
        try:
            pred = re.findall(r"\b[A-D]\b", output)[-1]  # TODO check if this is the best way to get the answer
        except IndexError:
            pred = None
    return pred == correct_answer


async def create_eval_chat(defense_id: str, model_name: str, user: models.User) -> str:
    secret = security.generate_random_ascii_string(6)
    chat_creation_data = schemas.ExistingDefenseChatCreate(defense_id=defense_id, model=model_name, secret=secret)
    new_chat_response = await api_v1.chat.create_chat_with_existing_defense(chat_creation_data, user)
    chat_id = new_chat_response.chat_id
    print(f"Chat ID: {chat_id}")
    return str(chat_id)


async def send_message(
    api_keys: schemas.LLMProviderAPIKeys | None, chat_id: str, prompt: str, user: models.User
) -> schemas.ChatResponse:
    new_message_data = schemas.GenerateRequest(api_keys=api_keys, new_message=prompt)
    chat = await deps.get_chat(id=chat_id, current_user=user)
    return await api_v1.chat.generate_new_message(new_message_data, chat, user)


async def ask_question(
    user: models.User,
    defense_id: str,
    model_name: str,
    api_keys: schemas.LLMProviderAPIKeys | None,
    prompt_1: str,
    prompt_2: str,
) -> schemas.ChatResponse:
    # Create DefenseChat and get chat_id
    chat_id = await create_eval_chat(defense_id, model_name, user)
    # First prompt
    await send_message(api_keys, chat_id, prompt_1, user)
    # Second prompt
    followup_response_data = await send_message(api_keys, chat_id, prompt_2, user)
    return followup_response_data


async def ask_question_multiturn(
    user: models.User,
    defense_id: str,
    model_name,
    api_keys,
    question,
    choices,
    subject,
) -> schemas.ChatResponse:
    # Create the initial prompt for the mult-turn interaction
    initial_prompt = format_question_multiturn(question, subject)

    # create chat given a defense
    chat_id = await create_eval_chat(defense_id, model_name, user)
    await send_message(api_keys, chat_id, initial_prompt, user)
    # Now, we send the choices one by one in multiple turns
    letters = ["A", "B", "C", "D"]
    assert len(letters) == len(choices) == 4
    for letter, choice in zip(letters, choices):
        followup_message = f"{letter}. {choice}"
        await send_message(api_keys, chat_id, followup_message, user)
    return await send_message(api_keys, chat_id, prompt_repeat_one_letter, user)


async def evaluate_utility_abcd_file(
    user: models.User,
    defense_id: str,
    model_name: str,
    api_keys: schemas.LLMProviderAPIKeys | None,
    questions_file: str,
    head_k: int | None = None,
    secret_seed: int = 0,
    multiturn: bool = False,
):
    random.seed(secret_seed)

    # Load questions from file
    tasks = pd.read_csv(questions_file, header=None, names=["question", "A", "B", "C", "D", "correct_answer"])
    tasks = tasks.to_dict("records")
    for i in range(len(tasks)):
        tasks[i]["index"] = i

    if head_k is not None:
        tasks = tasks[:head_k]

    # Determine subject from filename
    subject = Path(questions_file).stem.split(".")[0][: -len("_test")]
    print(f"Subject: {subject}")

    max_concurrent_tasks = 8
    semaphore = asyncio.Semaphore(max_concurrent_tasks)

    # Define the coroutine for processing each task
    async def process_task(task, sem):
        async with sem:  # Use semaphore to limit number of concurrent tasks
            print(
                f"Asking question {task['index']} in file {Path(questions_file).stem}, for defense {defense_id}, model {model_name}"
            )

            print(f"Asking question in file {Path(questions_file).stem}")
            question = task["question"]
            choices = [task["A"], task["B"], task["C"], task["D"]]
            correct_answer = task["correct_answer"]

            formatted_question = format_question_singleturn(question, choices, subject)

            if multiturn:
                final_response_data = await ask_question_multiturn(
                    user,
                    defense_id,
                    model_name,
                    api_keys,
                    question,
                    choices,
                    subject,
                )
            else:
                final_response_data = await ask_question(
                    user,
                    defense_id,
                    model_name,
                    api_keys,
                    prompt_1=formatted_question,
                    prompt_2=prompt_repeat_one_letter,
                )

            model_answer = final_response_data.history[-1].content

            return is_correct(model_answer, correct_answer)

    print(f"Running {len(tasks)} tasks")
    tasks_with_sem = [process_task(task, semaphore) for task in tasks]
    # Run the coroutines concurrently and collect results
    results = await asyncio.gather(*tasks_with_sem, return_exceptions=True)
    print("Results:", results)

    # Calculate and return the accuracy
    results_bool = [result for result in results if isinstance(result, bool)]
    errors = [result for result in results if not isinstance(result, bool)]
    print(f"Errors: {errors}")
    failed_cnt = len(errors)
    correct = sum(results_bool)
    total_bool = len(results_bool)

    # Return an exception if all tasks failed
    if total_bool == 0:
        print("All model conversations failed for at least one part of the evaluation")
        return results

    accuracy = correct / total_bool
    return {
        "acc": accuracy,  # on non-failed tasks
        "failed_cnt": failed_cnt,
        "total_bool": total_bool,
        "errors": errors,
    }


# %%
list_files_single = [
    "abstract_algebra_test.20.csv",
    "anatomy_test.20.csv",
    "astronomy_test.20.csv",
    "business_ethics_test.20.csv",
    "college_computer_science_test.20.csv",
    "college_mathematics_test.20.csv",
    "college_medicine_test.20.csv",
    "college_physics_test.20.csv",
    "computer_security_test.20.csv",
    "conceptual_physics_test.20.csv",
    "electrical_engineering_test.20.csv",
    "global_facts_test.20.csv",
    "high_school_chemistry_test.20.csv",
    "high_school_computer_science_test.20.csv",
    "high_school_european_history_test.20.csv",
    "high_school_geography_test.20.csv",
    "high_school_government_and_politics_test.20.csv",
    "high_school_macroeconomics_test.20.csv",
    "high_school_microeconomics_test.20.csv",
    "high_school_physics_test.20.csv",
    "high_school_psychology_test.20.csv",
    "high_school_statistics_test.20.csv",
    "high_school_us_history_test.20.csv",
    "international_law_test.20.csv",
    "jurisprudence_test.20.csv",
    "logical_fallacies_test.20.csv",
    "machine_learning_test.20.csv",
    "management_test.20.csv",
    "medical_genetics_test.20.csv",
    "miscellaneous_test.20.csv",
    "moral_disputes_test.20.csv",
    "nutrition_test.20.csv",
    "prehistory_test.20.csv",
    "professional_medicine_test.20.csv",
    "professional_psychology_test.20.csv",
    "public_relations_test.20.csv",
    "security_studies_test.20.csv",
    "sociology_test.20.csv",
    "us_foreign_policy_test.20.csv",
    "virology_test.20.csv",
    "world_religions_test.20.csv",
    "high_school_mathematics_test.20.csv",
    "arb_law_0.20.csv",
    "arb_law_1.20.csv",
    "arb_law_3.20.csv",
    "arb_law_4.20.csv",
    "arb_law_6.20.csv",
]

list_files_multiturn = [
    "clinical_knowledge_test.20.csv",
    "arb_law_5.20.csv",
    "arb_law_7.20.csv",
    "arb_law_8.20.csv",
    "arb_law_9.20.csv",
    "high_school_biology_test.20.csv",
    "marketing_test.20.csv",
    "philosophy_test.20.csv",
    "human_aging_test.20.csv",
    "elementary_mathematics_test.20.csv",
    "high_school_world_history_test.20.csv",
]


async def evaluate_utility_abcd(
    model_name: str,
    user: models.User,
    defense_id: str,
    api_keys: schemas.LLMProviderAPIKeys | None,
    head_k: int | None = None,
    multiturn: bool = False,
    is_test: bool = False,
) -> dict:
    print("defense_id:", defense_id, "api_keys:", api_keys)
    print(f"Model: {model_name}")
    tasks = []
    list_files = list_files_single if not multiturn else list_files_multiturn

    max_concurrent_files = 20
    semaphore = asyncio.Semaphore(max_concurrent_files)

    async def run_task(file):
        async with semaphore:
            questions_file = Path("/data/small_data") / file
            assert questions_file.exists(), "Questions file does not exist"
            return await evaluate_utility_abcd_file(
                user=user,
                defense_id=defense_id,
                model_name=model_name,
                api_keys=api_keys,
                questions_file=questions_file,
                head_k=head_k,
                multiturn=multiturn,
            )

    for file in list_files:
        task = asyncio.ensure_future(run_task(file))
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    print("Results:", results)
    if isinstance(results, list) and isinstance(results[0], list) and isinstance(results[0][0], Exception):
        raise results[0][0]

    accuracies = [result["acc"] for result in results if isinstance(result, dict)]
    failed_cnts = [result["failed_cnt"] for result in results if isinstance(result, dict)]
    total_bools = [result["total_bool"] for result in results if isinstance(result, dict)]
    error_lists = [result["errors"] for result in results if isinstance(result, dict)]
    errors = [error for error_list in error_lists for error in error_list]
    print(f"Errors: {errors}")

    def http_exception_to_string(exception) -> str:
        try:
            ret = f"HTTPException: Status code: {exception.status_code}, Detail: {exception.detail}"
        except AttributeError:
            ret = str(exception)
        return ret

    errors = [http_exception_to_string(error) for error in errors]
    print("Str errors:", errors)

    print(f"Failed counts: {failed_cnts}")
    print(f"Total bools: {total_bools}")
    print(f"Accuracies: {accuracies}")

    for i in range(len(accuracies)):
        if isinstance(accuracies[i], Exception):
            print(f"Task failed with exception: {str(accuracies[i])}")
            accuracies[i] = -1
        else:
            print(f"Accuracy: {accuracies[i]}")

    print(accuracies)
    dict_acc = dict(zip(list_files, accuracies))
    total_acc = (
        sum(acc for acc in accuracies if acc != -1) / len([acc for acc in accuracies if acc != -1])
        if (accuracies and len([acc for acc in accuracies if acc != -1]) > 0)
        else -1
    )

    pct_failed_qs = sum(failed_cnts) / (sum(total_bools) + sum(failed_cnts))
    return {
        "total_acc": total_acc,
        "accs": dict_acc,
        "k": head_k,
        "failed_cnts": " ".join([str(failed_cnt) for failed_cnt in failed_cnts]),
        "total_bools": " ".join([str(total_bool) for total_bool in total_bools]),
        "pct_failed_qs": pct_failed_qs,
        "errors": errors,
    }


# %%
