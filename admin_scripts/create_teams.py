import csv
from pathlib import Path

import click
import pandas as pd

from .admin_client import AdminClient, AdminClientSettings


def create_teams(filename: Path, budget: float, client: AdminClient):
    df = pd.read_csv(filename)
    teams_created = []
    all_users = client.get_users()
    users_emails_by_id = {str(user.id): user.email for user in all_users}
    for index, row in df.iterrows():
        team_name = row["Team name"]
        all_teams = client.get_teams()
        teams_names = {team.name for team in all_teams}
        if team_name in teams_names:
            print(f"Team {team_name} already exists")
            continue
        team_members_ids = [
            row[f"Team member {i} user ID"]
            for i in range(1, 6)
            if row[f"Team member {i} user ID"] and not pd.isna(row[f"Team member {i} user ID"])
        ]
        team_members = [users_emails_by_id[user_id] for user_id in team_members_ids]
        created_team = client.create_team(team_name)
        client.add_users_to_team(team_members, team_id=created_team.team_id)
        client.create_budget(created_team.team_id, budget_per_provider=budget)
        for member in team_members:
            teams_created.append({"team": team_name, "email": member, "budget": budget})
    result_path = filename.parent / "created" / f"{filename.stem}-created.csv"
    with open(result_path, "w") as f:
        csv.DictWriter(f, fieldnames=["team", "email", "budget"]).writeheader()
        csv.DictWriter(f, fieldnames=["team", "email", "budget"]).writerows(teams_created)


@click.command()
@click.option("--file_path", help="File with results from Google Form", type=Path)
@click.option("--budget", help="The budget for each team", type=str)
@click.option("--env_file", help=".env file to use", default=".env.admin", type=str)
def cli(file_path: Path, budget: float, env_file: str):
    create_teams(file_path, budget, AdminClient(AdminClientSettings(_env_file=env_file)))


if __name__ == "__main__":
    cli()
