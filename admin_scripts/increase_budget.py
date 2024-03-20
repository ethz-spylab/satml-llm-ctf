import click
import tqdm

from app import enums, schemas

from .admin_client import AdminClient, AdminClientSettings


def increase_budget(openai_budget: float, together_budget: float, client: AdminClient):
    teams_ids = [team.id for team in client.get_teams()]
    provider_budgets = {
        enums.APIProvider.openai: schemas.ProviderBudget(limit=openai_budget),
        enums.APIProvider.together: schemas.ProviderBudget(limit=together_budget),
    }
    for team_id in tqdm.tqdm(teams_ids):
        print(team_id)
        new_budget = client.increase_budget(team_id, provider_budgets=provider_budgets)
        print(new_budget)


@click.command()
@click.option("--openai_budget", help="The OpenAI for each team", type=str)
@click.option("--together_budget", help="The Together for each team", type=str)
@click.option("--env_file", help=".env file to use", default=".env.admin", type=str)
def cli(openai_budget: float, together_budget, env_file: str):
    increase_budget(openai_budget, together_budget, AdminClient(AdminClientSettings(_env_file=env_file)))


if __name__ == "__main__":
    cli()
