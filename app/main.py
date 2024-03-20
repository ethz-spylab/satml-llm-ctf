import logging
import traceback
from urllib.parse import quote

import gradio as gr
from beanie import init_beanie
from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi_oauth2.config import OAuth2Config
from fastapi_oauth2.exceptions import OAuth2InvalidRequestError
from fastapi_oauth2.middleware import OAuth2Middleware
from motor.motor_asyncio import AsyncIOMotorClient
from starlette import status
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from app import gradio, models
from app.api import deps
from app.api.api_v1.api import api_router
from app.api.api_v1.endpoints import oauth2
from app.api.documentation_text import api_description, tags_metadata
from app.config import settings
from app.enums import CompetitionPhase
from app.frontend import frontend_router
from app.security import ExistingUserWithProviderError, UserNotOnAllowListError, oauth2_clients, on_auth_success

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.project_name,
    openapi_url=f"{settings.api_v1_str}/openapi.json",
    openapi_tags=tags_metadata,
    description=api_description,
)

DB_MODELS = [
    models.APIKey,
    models.Chat,
    models.Defense,
    models.DefenseSubmission,
    models.User,
    models.Secret,
    models.SecretGuess,
    models.TeamBudget,
    models.Team,
]


@app.on_event("startup")
async def app_init():
    database_url = f"mongodb://{settings.mongodb_root_username}:{settings.mongodb_root_password.get_secret_value()}@{settings.database_url}"
    mongo_client = AsyncIOMotorClient(database_url)
    await init_beanie(mongo_client.get_default_database(), document_models=DB_MODELS)


@app.exception_handler(deps.NotAuthenticatedError)
def auth_exception_handler(request: Request, _: deps.NotAuthenticatedError):
    """
    Redirect the user to the login page if not logged in
    """
    if "/logout" not in request.url.path:
        redirect_url = quote(request.url.path, safe=":/%#?=@[]!$&'()*+,;")
        return RedirectResponse(url=f"/login?redirect_url={redirect_url}")
    return RedirectResponse(url="/")


@app.exception_handler(OAuth2InvalidRequestError)
def http_exception_handler(request: Request, exc: OAuth2InvalidRequestError):
    redirect_url = request.cookies.get("redirect_url")
    print(f"Failed login: {exc.detail}")
    redirect_url = quote(redirect_url, safe=":/%#?=@[]!$&'()*+,;") if redirect_url is not None else None
    redirect_url_parameter = f"&redirect_url={redirect_url}" if redirect_url is not None else ""
    return RedirectResponse(url=f"/login?retry=true{redirect_url_parameter}")


@app.exception_handler(AttributeError)
async def attribute_error_handler(request: Request, exc: AttributeError):
    traceback.print_tb(exc.__traceback__)
    print(exc)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


app = gr.mount_gradio_app(
    app,
    gradio.defense_interface,
    path="/defense",
    app_kwargs={
        "show_api": False,
        "dependencies": [Depends(deps.get_user_dependency_for_current_phase(CompetitionPhase.defense))],
        "exception_handlers": {deps.NotAuthenticatedError: auth_exception_handler},
        "include_in_schema": False,
        "docs_url": False,
        "redoc_url": False,
    },
)

# attack interface
app = gr.mount_gradio_app(
    app,
    gradio.attack_interface,
    path="/attack",
    app_kwargs={
        "show_api": False,
        "dependencies": [
            Depends(
                deps.get_user_dependency_for_current_phase(CompetitionPhase.reconnaissance, CompetitionPhase.evaluation)
            )
        ],
        "exception_handlers": {deps.NotAuthenticatedError: auth_exception_handler},
        "include_in_schema": False,
        "docs_url": False,
        "redoc_url": False,
    },
)


app.include_router(api_router, prefix=settings.api_v1_str)
app.include_router(frontend_router, prefix="", tags=["frontend"], include_in_schema=settings.hostname == "localhost")
app.include_router(oauth2.router, prefix="/oauth2", tags=["oauth2"], include_in_schema=settings.hostname == "localhost")
app.mount("/static", StaticFiles(directory="static"), name="static")


def wrong_provider_error_handler(request: Request, exc: Exception):
    response: RedirectResponse | HTMLResponse
    if isinstance(exc, ExistingUserWithProviderError):
        response = RedirectResponse(url=f"/login?correct_provider={exc.provider}")
    elif isinstance(exc, UserNotOnAllowListError):
        detail = f"""
        User {exc.email} not on allowlist. Reach out to
        <a href='mailto:edoardo.m.debenedetti@gmail.com'>edoardo.m.debenedetti@gmail.com</a> to be added to the
        allowlist. Go back to the <a href='/'>home</a>.
        """
        response = HTMLResponse(detail, status_code=status.HTTP_403_FORBIDDEN)
    else:
        return AuthenticationMiddleware.default_on_error(request, exc)
    response.delete_cookie("Authorization")
    return response


app.add_middleware(
    OAuth2Middleware,
    config=OAuth2Config(
        allow_http=settings.allow_insecure_http,
        jwt_secret=settings.secret_key.get_secret_value(),
        clients=oauth2_clients,
        jwt_expires=settings.jwt_expires,
        jwt_algorithm=settings.jwt_algorithm,
    ),
    callback=on_auth_success,
    on_error=wrong_provider_error_handler,
)
