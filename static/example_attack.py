import requests

# Replace with your actual CTF API key
ctf_api_key = "ctf_api_key"

# The base URL for the API
base_url = "https://ctf.spylab.ai/api/v1"

# ID of the defense you want to attack
target_defense_id = "target_defense_id"


def create_attack_chat(submission_id: str, evaluation: bool = False):
    endpoint = f"{base_url}/chat/attack/create"
    headers = {"accept": "application/json", "X-API-Key": ctf_api_key, "Content-Type": "application/json"}
    payload = {"submission_id": submission_id, "evaluation": evaluation}
    response = requests.post(endpoint, json=payload, headers=headers)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(e)
        raise e
    return response.json()


chat_info = create_attack_chat(submission_id=target_defense_id)
print(chat_info)


def get_remaining_guesses(secret_id: str):
    endpoint = f"{base_url}/secret/{secret_id}/remaining_guesses"
    headers = {"accept": "application/json", "X-API-Key": ctf_api_key, "Content-Type": "application/json"}
    response = requests.get(endpoint, headers=headers)
    return response.json()


print(get_remaining_guesses(secret_id=chat_info["secret_id"]))


def guess_secret(secret_id: str, chat_id: str, guess: str):
    endpoint = f"{base_url}/secret/{secret_id}/guess?guess={guess}"
    payload = {"chat_id": chat_id, "guess": guess}
    headers = {"accept": "application/json", "X-API-Key": ctf_api_key, "Content-Type": "application/json"}
    response = requests.post(endpoint, headers=headers, json=payload)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if not e.response.status_code == 403:
            print(e)
            raise e
        else:
            print("Guesses exhausted")
    return response.json()


print(guess_secret(chat_info["secret_id"], chat_id=chat_info["chat_id"], guess="123456"))
