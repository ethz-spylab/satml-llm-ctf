from collections import defaultdict
from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from jinja2 import BaseLoader, Environment
from starlette.responses import RedirectResponse

from app import enums, schemas
from app.api import api_v1, deps
from app.api.api_v1.endpoints.key import create_api_key as api_create_api_key
from app.api.api_v1.endpoints.key import revoke_api_key as api_revoke_api_key
from app.config import settings
from app.crud import api_key as crud_api_key
from app.enums import OAuth2SSOProvider

frontend_router = APIRouter()


NICE_PROVIDER_NAMES = {
    OAuth2SSOProvider.google: "Google",
    OAuth2SSOProvider.github: "GitHub",
}

HEADER = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/png" href="/static/favicon-32x32.png">
    <link rel="stylesheet" href="https://unpkg.com/mvp.css">
    <title>LLM CTF @ SaTML 2024 | {title}</title>
</head>
<body>
<header>
     <nav>
          <h1>LLM CTF @ SaTML 2024</h1>
          <ul>
              <li><a href="/">Home</a></li>
              <li><a href="/static/rules.pdf">Rules</a></li>
              <li><a href="/leaderboard/">Leaderboard</a></li>
              <li><a href="/attack/">Interface</a></li>
              <li><a href="/docs">API Docs</a></li>
              <li><a href="/api-key">API Key</a></li>
              <li><a target="_blank" href="https://github.com/ethz-spylab/satml-llms-ctf-issues">Issue tracker</a></li>
              <li><a href="https://docs.google.com/forms/d/e/1FAIpQLSc5lDXapW76S5yp3VylOpzsiOp8l2NgC-aHieYZiFXdLawvsw/viewform">Register Team</a></li>
              {% if not logged_in %}
                <li><a href="/login">Login</a></li>
              {% else %}
                <li><a href="/logout">Logout</a></li>
              {% endif %}
          </ul>
     </nav>
    <h1>{title}</h1>
</header>
<main>"""

CLOSING_TAGS = """
</main>
<script>
  let text = document.getElementById('apiKey').innerHTML;
  const copyContent = async () => {
    try {
      await navigator.clipboard.writeText(text);
      console.log('Content copied to clipboard');
    } catch (err) {
      console.error('Failed to copy: ', err);
    }
  }
</script>
</body>
</html>
"""


def make_page(title: str, body: str, logged_in: bool) -> HTMLResponse:
    header_template = Environment(loader=BaseLoader()).from_string(HEADER)
    header = header_template.render(logged_in=logged_in)
    return HTMLResponse(f"{header.format(title=title)}{body}{CLOSING_TAGS}")


templates = Jinja2Templates(directory="templates")


@frontend_router.head("/")
@frontend_router.get("/")
async def root(request: Request):
    logged_in = request.user.is_authenticated
    return templates.TemplateResponse("index.html", {"request": request, "logged_in": logged_in})


def sort_score_data(score_data: list[schemas.SubmissionScore]) -> list[schemas.SubmissionScore]:
    """
    Comparators:
    (1) Sort by score.value.
    (2) Sort by the sum of attacker points, increasing.
    (3) TODO Sort by the first submission time. This is hard to implement because schems.SubmissionScore does not have a submission timestamp.
    """
    # SubmissionScore(name='Team0Name/Model0Used', value=0.2, attackers=[AttackerScore(name='Attacker0Name', points=314), AttackerScore(name='Attacker1Name', points=225)])
    return sorted(score_data, key=lambda x: (-x.value, sum([attacker.points for attacker in x.attackers])))


@frontend_router.get("/leaderboard", response_class=HTMLResponse)
async def get_leaderboard_page(
    request: Request, redis_client: Annotated[redis.Redis, Depends(deps.get_redis_client)], response: Response
):
    score_data = await api_v1.scores.get_scores(redis_client, response)
    score_data = sort_score_data(score_data)

    linear_attacker_scores: dict[str, list[int]] = defaultdict(list)
    attacker_scores: dict[str, dict[str, float]] = {}

    total_submissions = len(score_data)
    submissions_to_count = total_submissions - settings.max_submissions_per_team

    # Iterate through the dummy_scores
    for submission_score in score_data:
        attacker_scores[submission_score.name] = {}
        for attacker_score in submission_score.attackers:
            attacker_scores[submission_score.name][attacker_score.name] = attacker_score.points
            # Accumulate points for each attacker
            linear_attacker_scores[attacker_score.name].append(attacker_score.points)

    attacker_totals = {
        k: sum(sorted(v, reverse=True)[:submissions_to_count]) for k, v in linear_attacker_scores.items()
    }

    sorted_attacker_totals = dict(sorted(attacker_totals.items(), key=lambda x: x[1], reverse=True))

    attacker_names = [name for name, _ in sorted_attacker_totals.items()]

    base_url = settings.base_url

    if base_url.endswith("localhost"):
        base_url = f"{base_url}:8008"

    score_api_url = f"{base_url}{settings.api_v1_str}{frontend_router.prefix}/scores"

    body_html = templates.TemplateResponse(
        "leaderboard.html",
        {
            "request": request,
            "score_data": score_data,
            "attacker_names": attacker_names,
            "score_api_url": score_api_url,
            "attacker_totals": attacker_totals,
            "attacker_scores": attacker_scores,
        },
    ).body.decode("utf-8")
    response = make_page("", body=body_html, logged_in=request.user.is_authenticated)
    return response


@frontend_router.get("/security.txt", response_class=PlainTextResponse)
def security_txt():
    data = (
        "To disclose security vulnerabilities, please contact Edoardo Debenedetti at "
        "the email address found at https://edoardo.science. Thanks!"
    )
    return data


@frontend_router.get("/login")
def login(
    request: Request,
    redirect_url: str | None = None,
    retry: bool | None = None,
    correct_provider: enums.OAuth2SSOProvider | None = None,
):
    if request.user.is_authenticated and redirect_url is not None:
        return RedirectResponse(redirect_url)
    if request.user.is_authenticated:
        body = (
            f"<p>You are already logged in as {request.user.email}. Go back to the <a href='/'>home page</a>, or "
            "logout <a href='/oauth2/logout'>here</a>.</p>"
        )
        return make_page(title="Login", body=body, logged_in=request.user.is_authenticated)

    body = (
        f'<p>Log In with <a href="/oauth2/{OAuth2SSOProvider.google.value}/authorize">Google</a> or <a'
        f' href="/oauth2/{OAuth2SSOProvider.github.value}/authorize">GitHub</a>.</p>'
    )
    if redirect_url is not None:
        title = "Login first"
        body = (
            f"<p>You need to be logged in to access <code>{redirect_url}</code>."
            " You will be redirected after logging in.</p>" + body
        )
    else:
        title = "Login"
    if retry is not None and retry:
        body = "<p>Sorry, the previous login attempt failed for an unknown error. Please try again.</p>" + body
    if correct_provider is not None:
        body = (
            "<p>Sorry, the previous login attempt failed because you previously created your account with"
            f" {NICE_PROVIDER_NAMES[correct_provider]} as a provider."
            f" Please try again by logging in with {NICE_PROVIDER_NAMES[correct_provider]}.</p>"
        ) + body

    response = make_page(title=title, body=body, logged_in=request.user.is_authenticated)
    if redirect_url is not None:
        response.set_cookie("redirect_url", redirect_url)
    return response


@frontend_router.get("/logout")
def logout(_: deps.ActiveUserBearerDep):
    return RedirectResponse("/oauth2/logout")


@frontend_router.get("/api-key")
async def api_key_page(request: Request, user: deps.ActiveUserBearerDep):
    title = "API Key"
    assert user.id is not None
    api_key = await crud_api_key.get_by_user(user_id=user.id)
    if api_key is not None:
        api_key_string = f"""
<p>Your API key is <i id='apiKey'>{api_key.key}</i>,
it was generated on {api_key.created.strftime("%Y-%m-%d %H:%M:%S")} UTC.</p>
<center>
<button class='btn' onclick='copyContent()'>Click to copy the API key to your clipboard</button>
</center>
<p>Revoke it <a href='/revoke-api-key'>here</a> if needed.</p>"""
    else:
        api_key_string = "Generate an API key <a href='/create-api-key'>here</a>."
    body = f"""
<p>Logged in as {request.user.email}, your user id is "{user.id}".
Log out <a href='/oauth2/logout'>here</a>.</p>
<p>{api_key_string}</p>
"""
    return make_page(title, body, logged_in=request.user.is_authenticated)


@frontend_router.get("/create-api-key")
async def create_api_key(current_user: deps.ActiveUserBearerDep):
    api_key: schemas.APIKey | None
    try:
        api_key = await api_create_api_key(current_user=current_user)
    except HTTPException:
        assert current_user.id is not None
        api_key = await crud_api_key.get_by_user(user_id=current_user.id)
    assert api_key is not None
    return RedirectResponse("/api-key")


@frontend_router.get("/revoke-api-key")
async def revoke_api_key(current_user: deps.ActiveUserBearerDep):
    await api_revoke_api_key(current_user=current_user)
    body = """
<p>API key revoked. You can go back to the <a href='/'>home page</a>.</p>
"""
    return make_page("API Key", body, logged_in=True)
