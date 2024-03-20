import os

import gradio as gr
from beanie import PydanticObjectId
from fastapi import HTTPException

from app import enums, schemas
from app.api import api_v1, deps
from app.api.api_v1.endpoints.secret import get_remaining_guesses, guess_secret
from app.api.api_v1.endpoints.submission import get_all_submissions
from app.config import settings
from app.gradio.defense import get_user

OPENAI_API_KEY = ""  # for debugging purposes


async def format_defenses_dropdown(
    defenses: list[schemas.AttackerDefenseSubmissionInfo], current_user: schemas.User
) -> list[tuple[str, str]]:
    # Return (key, value) tuples where value is only defense_id
    formatted_defenses = []

    for defense in defenses:
        displayed_id = defense.id
        display_text = f"{defense.team_name}, {defense.model.value}"
        formatted_defenses.append((f"{display_text}", str(displayed_id)))

    return formatted_defenses


async def load_defenses(request: gr.Request, load_team_defenses: bool = True):
    try:
        current_user = await get_user(request)
    except HTTPException as e:
        raise gr.Error(f"Authentication failed: {e.detail}")
    assert current_user.is_active, "Your user is disabled"

    return await format_defenses_dropdown(
        # TODO: implement this properly
        await get_all_submissions(current_user, skip=0, limit=100),
        current_user,
    )


async def create_chat(
    request: gr.Request,
    submission_id: str,
) -> tuple[str, str, str]:
    try:
        current_user = await get_user(request)
    except HTTPException as e:
        raise gr.Error(f"Authentication failed: {e.detail}")
    assert current_user.is_active

    attack_chat_create_data = schemas.AttackChatCreate(submission_id=PydanticObjectId(submission_id), evaluation=False)
    new_chat = await api_v1.endpoints.chat.create_attack_chat(attack_chat_create_data, current_user)

    assert new_chat is not None, "Error creating your chat"

    return str(new_chat.chat_id), str(new_chat.submission_id), str(new_chat.secret_id)


def chatbot_from_history(history: list[schemas.AttackMessage]) -> list[tuple[str, str]]:
    chatbot = []
    system_messages: list[schemas.AttackMessage] = []

    for message in history:
        if message.role == enums.ChatRole.user:
            if len(system_messages) > 0:
                chatbot.append([None, system_messages[-1].content])
                system_messages = []

            chatbot.append((message.content, None))

        else:
            system_messages.append(message)

    if len(system_messages) > 0:
        chatbot.append((None, system_messages[-1].content))

    return chatbot


async def predict(
    chatbot,
    chat_id: str,
    openai_api_key: str | None,
    together_api_key: str | None,
    request: gr.Request,
):
    last_message = chatbot[-1][0]
    try:
        current_user = await get_user(request)
    except HTTPException as e:
        raise gr.Error(f"Authentication failed: {e.detail}")
    current_chat = await deps.get_chat(chat_id, current_user)
    if openai_api_key == "":
        openai_api_key = None
    if together_api_key == "":
        together_api_key = None
    api_keys = schemas.LLMProviderAPIKeys(openai=openai_api_key, together=together_api_key)
    generation_request = schemas.GenerateRequest(new_message=last_message, api_keys=api_keys)
    try:
        updated_chat = await api_v1.chat.generate_new_attack_message(generation_request, current_chat, current_user)
    except HTTPException as e:
        raise gr.Error(f"Error generating a new message: {e.detail}")
    return chatbot_from_history(updated_chat.history)


def on_change_defense_selector(defense_selected):
    return {
        selected_defense_id: gr.update(value=defense_selected),
    }


async def setup_user(load_team_defenses: bool, request: gr.Request):
    print("Setting up user...", request)
    _ = await get_user(request)
    defenses_db = await load_defenses(request, load_team_defenses)
    return {
        together_api_key_box: gr.update(interactive=True),
        openai_api_key_box: gr.update(interactive=True),
        setup_btn: gr.update(visible=False),
        defense_row: gr.update(visible=True),
        user_defenses: gr.update(value=False),
        defense_selector: gr.update(choices=[("", "")] + defenses_db, value=""),
    }


async def get_guesses(secret_id: str, request: gr.Request):
    try:
        current_user = await get_user(request)
    except HTTPException as e:
        raise gr.Error(f"Authentication failed: {e.detail}")
    assert current_user.is_active

    guesses_remaining_dict = await get_remaining_guesses(
        secret_id=PydanticObjectId(secret_id), current_user=current_user
    )
    guesses_remaining = guesses_remaining_dict["guesses_remaining"]
    return guesses_remaining


CUSTOM_CSS = """
.wrap .wrap input:disabled {
    box-shadow: none !important;
}

:disabled {
    box-shadow: none !important;
}
"""


with gr.Blocks(theme=gr.themes.Soft(), css=CUSTOM_CSS) as attack_interface:
    gr.HTML('<h1 align="center">SaTML LLMs CTF: Reconnaissance Phase</h1>')
    user_defenses = gr.State(value=[])
    selected_defense_id = gr.State(value="")
    gr.HTML(
        '<h3 align="center">By using this chat interface, you accept that the interactions with the interface and the '
        "API can be used for research purposes, and potentially open-sourced by the competition organizers. Note that you won't be able to delete attack chats by yourself!</h3>"
    )
    print("Hostname:", settings.hostname, flush=True)
    print("OpenAI API key:", os.environ.get("OPENAI_API_KEY", ""), flush=True)
    print("OpenAI API key:", OPENAI_API_KEY, flush=True)
    with gr.Row() as api_row:
        openai_api_key_box = gr.Textbox(
            label="Insert your OpenAI API key if you want to use your own credits.",
            value=OPENAI_API_KEY if settings.hostname == "localhost" else "",
        )
        together_api_key_box = gr.Textbox(
            label="Insert your Together API key if you want to use your own credits.",
        )
    gr.HTML("<p>We don't store your API keys.</p>")
    setup_btn = gr.Button("Set-up chat")

    with gr.Row(visible=False) as defense_row:
        defense_selector = gr.Dropdown(
            label="Select a defense to attack", choices=[], interactive=True, elem_classes=["dropdown"]
        )
        launch_chat_btn = gr.Button("Load defense")

    with gr.Column(visible=False) as attack_column:
        chatbot_box = gr.Chatbot()
        msg_box = gr.Textbox(label="Your message")
        submit_btn = gr.Button("Submit (or press enter)")
        restart_attack_btn = gr.Button("Restart Attack")

        secret_input_box = gr.Textbox(label="Enter Secret", placeholder="Type the secret here...", lines=1)
        check_secret_btn = gr.Button("Check Secret (or press enter)")

        with gr.Row() as secret_row:
            guesses_remaining_label = gr.Textbox(label="Guesses remaining:", interactive=False)
            submission_id_box = gr.Textbox(label="Submission ID:", interactive=False)
            secret_id_display = gr.Textbox(label="Secret ID:", interactive=False)
            chat_id_box = gr.Textbox(label="Chat ID:", interactive=False)

    # Button to set up the user
    setup_btn.click(
        fn=setup_user,
        inputs=[setup_btn],
        outputs=[
            together_api_key_box,
            openai_api_key_box,
            setup_btn,
            secret_input_box,
            defense_row,
            defense_selector,
            user_defenses,
        ],
    )

    defense_selector.change(on_change_defense_selector, [defense_selector], [selected_defense_id], queue=False)

    async def launch_fn(
        submission_id: str,
        request: gr.Request,
    ):
        chat_id, _, secret_id = await create_chat(request, submission_id)

        return {
            attack_column: gr.update(visible=True),
            launch_chat_btn: gr.update(visible=False),
            chat_id_box: gr.update(value=chat_id),
            submission_id_box: gr.update(value=submission_id),
            restart_attack_btn: gr.update(visible=True),
            secret_input_box: gr.update(value="", interactive=True),
            secret_id_display: gr.update(value=secret_id),
            guesses_remaining_label: gr.update(value=await get_guesses(secret_id, request)),
            check_secret_btn: gr.update(visible=True),
            defense_selector: gr.update(interactive=False),
        }

    launch_chat_components = [
        attack_column,
        launch_chat_btn,
        chatbot_box,
        chat_id_box,
        submission_id_box,
        msg_box,
        submit_btn,
        restart_attack_btn,
        secret_input_box,
        secret_id_display,
        guesses_remaining_label,
        check_secret_btn,
        defense_selector,
    ]

    # Button to load the selected defense
    launch_chat_btn.click(
        fn=launch_fn,  # Function to call when button is clicked
        inputs=[defense_selector],  # Input from the defense selector dropdown
        outputs=launch_chat_components,
    )

    def user(user_message, history):
        return "", history + [[user_message, None]]

    msg_box.submit(user, [msg_box, chatbot_box], [msg_box, chatbot_box], queue=False).success(
        fn=predict,
        inputs=[chatbot_box, chat_id_box, openai_api_key_box, together_api_key_box],
        outputs=[chatbot_box],
        queue=False,
    )

    submit_btn.click(user, [msg_box, chatbot_box], [msg_box, chatbot_box], queue=False).success(
        fn=predict,
        inputs=[chatbot_box, chat_id_box, openai_api_key_box, together_api_key_box],
        outputs=[chatbot_box],
        queue=False,
    )

    async def restart_fn(
        defense_selector: str,
        request: gr.Request,
    ):
        print(f"defense_selector: {defense_selector}", flush=True)
        ret = await launch_fn(
            defense_selector,
            request,
        )
        print(f"ret: {ret}", flush=True)
        return {
            **ret,
            chatbot_box: gr.Chatbot(value=[]),
        }

    restart_attack_btn.click(
        fn=restart_fn,
        inputs=[
            defense_selector,  # we have to pass it so it's converted to a string
        ],
        outputs=launch_chat_components,
        queue=False,
    )

    with gr.Row(visible=False) as secret_guessed_correctly_row:
        secret_guessed_correctly_label = gr.Textbox(label="Secret guessed correctly!", interactive=False)

    async def check_secret_fn(secret_id: str, secret_input_str: str, chat_id: str, request: gr.Request):
        try:
            current_user = await get_user(request)
        except HTTPException as e:
            raise gr.Error(f"Authentication failed: {e.detail}")
        assert current_user.is_active

        print(f"secret_id: {secret_id}", flush=True)
        print(f"secret_input: {secret_input_str}", flush=True)

        try:
            secret_guess_request = schemas.SecretGuessRequest(guess=secret_input_str, chat_id=chat_id)
        except Exception as e:
            gr.Warning(f"Error: {e}")
            return {
                guesses_remaining_label: gr.update(value=await get_guesses(secret_id, request)),
                secret_input_box: gr.update(value="", interactive=True),
                check_secret_btn: gr.update(visible=True),
            }

        check_secret_response = await guess_secret(PydanticObjectId(secret_id), secret_guess_request, current_user)
        print(f"check_secret_response: {check_secret_response}", flush=True)
        if check_secret_response.correct:
            gr.Info("Correct secret!")
            return {
                secret_guessed_correctly_row: gr.update(visible=True),
                guesses_remaining_label: gr.update(value=check_secret_response.guesses_remaining),
                secret_input_box: gr.update(value=secret_input_str, interactive=False),
                check_secret_btn: gr.update(visible=False),
            }
        gr.Warning("Wrong secret!")
        return {
            guesses_remaining_label: gr.update(value=check_secret_response.guesses_remaining),
            secret_input_box: gr.update(value="", interactive=True),
            check_secret_btn: gr.update(visible=True),
        }

    secret_input_box.submit(
        fn=check_secret_fn,
        inputs=[
            secret_id_display,
            secret_input_box,
            chat_id_box,
        ],
        outputs=[
            secret_guessed_correctly_row,
            guesses_remaining_label,
            secret_input_box,
            check_secret_btn,
        ],
        queue=True,
    )

    check_secret_btn.click(
        fn=check_secret_fn,
        inputs=[
            secret_id_display,
            secret_input_box,
            chat_id_box,
        ],
        outputs=[
            secret_guessed_correctly_row,
            guesses_remaining_label,
            secret_input_box,
            check_secret_btn,
        ],
        queue=True,
    )


attack_interface.show_api = False
attack_interface.blocked_paths = ["app", "requirements.txt"]
attack_interface.title = "LLMs CTF Reconnaissance"
