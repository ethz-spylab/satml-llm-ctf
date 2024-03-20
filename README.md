# LLM CTF

This is the code used to run the [2024 SaTML LLM CTF](https://ctf.spylab.ai/). The code was developed from scratch by:

- [Edoardo Debenedetti](https://github.com/dedeswim)
- [Daniel Paleka](https://github.com/dpaleka)
- [Javier Rando](https://github.com/javirandor)
- [@nustom](https://github.com/nustom) (hired with the support of [BERI](https://existence.org/))

The app as a [FastAPI](https://fastapi.tiangolo.com/) web server, with a [MongoDB](https://www.mongodb.com) database,
and a [Redis](https://redis.io/) cache. The web server is served by [Uvicorn](https://www.uvicorn.org/). Everything runs
in [Docker](https://www.docker.com/) and `docker compose`.

Note that the platform was developed while the competition was running, so not all design decisions were optimal.

We ran the application on a single Google Cloud VM with 64GB of RAM and 32 vCPUs. This was enough for most of the
competition, but the most heated phases were running a bit too slow.

Some potential improvements that could be done to the platform (PRs welcome!) are:

- [ ] Move to a relational DB, as DB operations turned out to be more relational than we expected when we first started
the project.
- [ ] Write **real** tests for the code. Currently, we have some form of [integration tests](tests/basic_api_test.py)
that test the API, but we don't have any unit tests.
- [ ] Make the whole repo more templetable, so that it can be used as a starting point for other CTFs and similar projects.
- [ ] Simplify the slight mess in [`app/schemas`](app/schemas). Currently, there is some redundancy in the schema classes.
- [ ] Move from `docker compose` to `kubernetes` or something similar for better scalability and reliability.

## Setting up the environment

1. Create a `.env` file with the same content as `.env.example`, and change the values as needed.
2. Create a `.env.prod` file with the same content as `.env.example`, and change the values as needed.
3. Create a `.secrets` folder with the same content as `secrets.example`, and change the values as instructed in each file.

## How to (re)start the application

```
docker compose --env-file .env.prod -f compose.prod.yml up --build -d
```

or

```
docker compose --env-file .env.prod -f compose.prod.yml up --build -d web
```

To only start the web service container. If the container(s) are already running, then they will be re-built and re-started.

### Development

```bash
docker compose up --build -d web
```

### Production

```bash
docker compose --env-file .env.prod -f compose.prod.yml up --build -d web
```

### Stopping

```bash
docker compose down
```

Use `web` if you want to start the app, otherwise don't specify to start everything

### Checking the logs

```bash
docker compose logs -f
```

The `-f` flag behaves like in `cat`.

## Linting and code style

Lint with

```bash
ruff check --fix .
```

Format with

```bash
ruff format .
```

Check types with

```bash
mypy .
```
