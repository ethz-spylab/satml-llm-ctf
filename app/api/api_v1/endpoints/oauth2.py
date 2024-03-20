from urllib.parse import quote

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.enums import OAuth2SSOProvider

router = APIRouter()


@router.get("/{provider}/authorize")
def authorize(request: Request, provider: OAuth2SSOProvider):
    if request.auth.ssr:
        return request.auth.clients[provider.value].authorization_redirect(request)
    return dict(url=request.auth.clients[provider.value].authorization_url(request))


@router.get("/{provider}/token")
async def token(request: Request, provider: OAuth2SSOProvider):
    if request.auth.ssr:
        redirect_url = request.cookies.get("redirect_url")
        response = await request.auth.clients[provider.value].token_redirect(request)
        response.headers["location"] = quote(
            str(redirect_url) if redirect_url is not None else "/", safe=":/%#?=@[]!$&'()*+,;"
        )
        response.delete_cookie("redirect_url")
        return response
    return await request.auth.clients[provider.value].token_data(request)


@router.get("/logout")
def logout(request: Request):
    response = RedirectResponse(request.base_url)
    response.delete_cookie("Authorization")
    return response
