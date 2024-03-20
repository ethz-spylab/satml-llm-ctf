from app.config import settings

api_description = f"""
Welcome to the LLMs CTF hosted at SaTML 2024. Find all the details and instructions for the competition [here](/static/rules.pdf).

This page contains an interactive API documentation. Remember, most functionalities are also available through [our interface](/defense).

### Interacting with the documentation
To use the endpoints through this documentation page, you need to:
1. Obtain your API key from [{settings.base_url}/api-key](/api-key)
2. Click on the Authorize button below and paste the API key.

After that, you can open any endpoint and click "Try it out" to make requests with our templates.

⚠️ The endpoints for **generation** and **utility evaluation** will consume credits from your Team Budget, or from your API keys if provided. 

**By using this API, you accept that the interactions with the interface and the API can be used for research purposes, and potentially open-sourced by the competition organizers.**

We provide example Python scripts that create and interact with a defense through the API for both the attack and defense phases: [example_defense.py](/static/example_defense.py), [example_attack.py](/static/example_attack.py).

For the attack phase, you can retrieve the submissions to attack via the `/api/v1/submissions` endpoint.
"""


tags_metadata = [
    {
        "name": "chat/attack",
        "description": "These endpoints allow you to create *chats*. A chat can be created to interact with a submission. Once a chat is created, you can prompt the model to obtain new messages in the conversation.",
    },
    {
        "name": "chat/defense",
        "description": "These endpoints allow you to create *CHATS* and *DEFENSES*. A chat can be created to interact with an existing defense or along with a new defense. Once a chat is created, you can prompt the model to obtain new messages in the conversation.",
    },
    {
        "name": "submission",
        "description": "List submissions to attack. Submissions are shuffled in a different way for each team to prevent the same submissions to be attacked by everyone.",
    },
    {
        "name": "secret",
        "description": "Guess a secret given the secret ID, see your past guesses, and how many guesses you have left for the secret.",
    },
    {
        "name": "budget",
        "description": "Check the remaining budget for your team",
    },
    {
        "name": "models",
        "description": "List models available for the chats.",
    },
    {
        "name": "defense",
        "description": "List, see and remove your existing defenses. You can also submit your defense for the next phase.",
    },
]
