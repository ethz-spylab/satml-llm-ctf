# ruff: noqa
# mypy: ignore-errors

# %%
import json
from pathlib import Path
import click
import asyncio

import requests

from dotenv import load_dotenv
import os

from requests import HTTPError

load_dotenv(override=True)
openai_key = os.getenv("OPENAI_KEY")
together_key = os.getenv("TOGETHER_KEY")
auth_key = os.getenv("AUTH_KEY")
api_keys = {"openai": openai_key, "together": together_key}


async def evaluate_utility_abcd(
    base_url: str,
    small: bool,
    api_key: str,
    defense_id: str,
    api_keys: dict[str, str | None],
    model: str = "openai/gpt-3.5-turbo-1106",
    is_test: bool = False,
):
    url = f"{base_url}/api/v1/defense/{defense_id}/evaluate-utility?is_test={is_test}"
    headers = {"accept": "application/json", "X-API-Key": api_key, "Content-Type": "application/json"}
    data = {
        "model": model,
        "api_keys": api_keys,
        "small": small,
    }
    print("Running request")
    response = requests.post(url, headers=headers, json=data)
    try:
        response.raise_for_status()
    except HTTPError as e:
        print(e.response.text)
        exit(1)
    response_json = response.json()
    return response_json


def get_all_utility_evaluations(base_url: str, api_key: str, defense_id: str):
    url = f"{base_url}/api/v1/defense/{defense_id}/list-utility-evals"
    print("Running request", url)
    headers = {"accept": "application/json", "X-API-Key": api_key, "Content-Type": "application/json"}
    response = requests.get(url, headers=headers)
    try:
        response.raise_for_status()
    except HTTPError as e:
        print(e.response.text)
        exit(1)
    response_json = response.json()
    return response_json


def create_defense_get_id(api_key, defense_prompt, output_filters, base_url) -> str:
    """
    Create a defense for the first time.
    Returns the defense id.
    """
    url = f"{base_url}/api/v1/defense/create"
    headers = {"accept": "application/json", "X-API-Key": api_key, "Content-Type": "application/json"}
    data = {"defense_prompt": defense_prompt, "output_filters": output_filters}
    print("Running request")
    print(f"URL: {url} \nHeaders: {headers} \nData: {data}")
    response = requests.post(url, headers=headers, json=data)
    try:
        response.raise_for_status()
    except HTTPError as e:
        print(e.response.text)
        exit(1)
    response_json = response.json()
    defense_id = response_json["id"]
    print(f"Defense ID: {defense_id}")
    return defense_id


async def main(small: bool, base_url: str, force_rerun: bool, is_test: bool, submissions_file: Path):
    assert submissions_file.exists()
    """
    {
        "model": "meta/llama-2-70b-chat",
        "test_id": "65b24b2554ed7c7ff8f16204",
        "id": "65b24b2554ed7c7ff8f16305",
        "team_name": "Team Name",
        "created": false,
        "defense": {
            "defense_prompt": "",
            "output_filters": [],
            "name": "Blank",
            "id": "659e449abfcdf6538aece57f",
            "user": "658e95c7435a31f382df1b3f"
        },
    }
    """

    with open(submissions_file) as f:
        submissions = json.load(f)

    accs_file = Path("../accs.json")
    results = [] if not accs_file.exists() else json.load(open(accs_file))

    # create all defenses which are not created; resave defenses.json
    for submission in submissions:
        defense_id = submission.get("test_id", None)
        created = submission.get("created", False)
        defense_prompt = submission["defense"]["defense_prompt"]
        output_filters = submission["defense"]["output_filters"]

        if force_rerun or not created:
            defense_id = create_defense_get_id(auth_key, defense_prompt, output_filters, base_url)
            submission["test_id"] = defense_id
            submission["created"] = True
            print(f"Created Defense ID: {defense_id}")
        else:
            assert defense_id is not None
            print(f"Defense ID: {defense_id} already created")

    with open(submissions_file, "w") as f:
        json.dump(submissions, f, indent=4)

    submissions_to_test = []

    for submission in submissions:
        defense_id = submission["test_id"]
        defense_prompt = submission["defense"]["defense_prompt"]
        output_filters = submission["defense"]["output_filters"]
        model = submission["model"]

        if not force_rerun and (submission["created"] or defense_id in [result["test_id"] for result in results]):
            print(f"Skipping Defense ID: {defense_id}")
            continue

        print(f"Testing Defense ID: {defense_id}")
        print(f"Defense Prompt: {defense_prompt}")
        print(f"Output Filters: {output_filters}")

        submissions_to_test.append(submission)

    async def evaluate_submission(semaphore, submission):
        async with semaphore:
            result = submission.copy()
            model = submission["model"]
            defense_id = submission["test_id"]

            if model == "openai/gpt-3.5-turbo-1106":
                result["accuracy_openai"] = await evaluate_utility_abcd(
                    base_url=base_url,
                    small=small,
                    api_key=auth_key,
                    defense_id=defense_id,
                    model="openai/gpt-3.5-turbo-1106",
                    api_keys=api_keys,
                    is_test=is_test,
                )  # type: ignore

            elif model == "meta/llama-2-70b-chat":
                result["accuracy_together"] = await evaluate_utility_abcd(
                    base_url=base_url,
                    small=small,
                    api_key=auth_key,
                    defense_id=defense_id,
                    model="meta/llama-2-70b-chat",
                    api_keys=api_keys,
                    is_test=is_test,
                )  # type: ignore

            print(f"Result: {json.dumps(result, indent=4)}")
            return result

    semaphore = asyncio.Semaphore(50)  # Adjust the number as needed for concurrency limit

    tasks = [evaluate_submission(semaphore, submission) for submission in submissions_to_test]
    results = await asyncio.gather(*tasks)

    with open(accs_file, "w") as f:
        json.dump(results, f, indent=4)

    print("Listing all utility evaluations")
    for submission in submissions:
        # list all utility evaluations
        print("\nTeam Name: ", submission["team_name"])
        print("Model: ", submission["model"])
        print("Defense ID: ", submission["test_id"])
        utility_evaluations = get_all_utility_evaluations(
            base_url=base_url, api_key=auth_key, defense_id=submission["test_id"]
        )
        for utility_evaluation in utility_evaluations:
            utility_evaluation["result"].pop("additional_info", None)

        print(f"Utility evaluations: {json.dumps(utility_evaluations, indent=4)}")


# Can't directly use click on async functions
@click.command()
@click.option("--small", is_flag=True, help="Flag to use small data.")
@click.option("--base_url", default="http://localhost:8008", help="The url to call.", type=str)
@click.option("--force_rerun", is_flag=True, help="Flag to force rerun all defenses.")
@click.option("--is_test", is_flag=True, help="Use test mode.")
@click.option("--submissions_file", default="defenses.json", help="Path to defenses file.")
def cli(small: bool, base_url: str, force_rerun: bool, is_test: bool, submissions_file: str):
    asyncio.run(main(small, base_url, force_rerun, is_test, Path(submissions_file)))


if __name__ == "__main__":
    cli()
