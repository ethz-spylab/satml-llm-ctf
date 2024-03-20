import secrets
import string

from fastapi import HTTPException
from fastapi_oauth2.claims import Claims
from fastapi_oauth2.client import OAuth2Client
from fastapi_oauth2.middleware import Auth
from fastapi_oauth2.middleware import User as OAuth2User
from passlib.context import CryptContext
from social_core.backends.github import GithubOAuth2
from social_core.backends.google import GoogleOAuth2
from starlette import status
from starlette.authentication import AuthenticationError

from app import crud, schemas
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_api_key() -> str:
    key = secrets.token_urlsafe(settings.api_key_length)
    return key


def hash_api_key(key: str) -> str:
    return pwd_context.hash(key)


def verify_api_key(plain_api_key, hashed_api_key):
    return pwd_context.verify(plain_api_key, hashed_api_key)


class CustomGoogleOAuth2(GoogleOAuth2):
    name = "google"


oauth2_clients = [
    OAuth2Client(
        backend=CustomGoogleOAuth2,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scope=["openid", "email"],
        claims=Claims(
            identity=lambda user: f"{user.provider}:{user.sub}",
        ),
    ),
    OAuth2Client(
        backend=GithubOAuth2,
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        scope=["user:email"],
        claims=Claims(
            identity=lambda user: f"{user.provider}:{user.id}",
        ),
    ),
]


class ExistingUserWithProviderError(AuthenticationError):
    def __init__(self, email: str, provider: str):
        self.provider = provider
        self.email = email


class UserNotOnAllowListError(AuthenticationError):
    def __init__(self, email: str):
        self.email = email


async def on_auth_success(auth: Auth, user: OAuth2User):
    if not user.is_authenticated:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Could not validate credentials via SSO")
    if settings.use_emails_allowlist and user.email.lower() not in settings.allowed_emails:
        raise UserNotOnAllowListError(user.email)
    existing_user_email = await crud.user.get_by_email(email=user.email)
    existing_user_openid_id = await crud.user.get_by_openid_id(openid_id=user.identity)
    if existing_user_email is not None:
        if existing_user_email.provider != auth.provider.provider:
            raise ExistingUserWithProviderError(email=user.email, provider=existing_user_email.provider.value)
    elif existing_user_openid_id is not None and existing_user_openid_id.email != user.email:
        await crud.user.update(
            db_obj=existing_user_openid_id,
            obj_in=schemas.UserUpdate(email=user.email, provider=auth.provider.provider, openid_id=user.identity),
        )
    else:
        user_create = schemas.UserCreate(
            email=user.email,
            provider=auth.provider.provider,
            openid_id=user.identity,
        )
        await crud.user.create(obj_in=user_create)


DEFAULT_SECRET_SPACE = string.ascii_letters + string.digits


def generate_random_ascii_string(length: int, secret_space: str = DEFAULT_SECRET_SPACE) -> str:
    return "".join(secrets.choice(secret_space) for _ in range(length))
