import os
import requests
from datetime import datetime, timedelta
import pytz

METS_ID = 121
GUARDIANS_ID = 114
TEAM_NAMES = {METS_ID: "Mets", GUARDIANS_ID: "Guardians"}


def get_eastern_now():
    return datetime.now(pytz.timezone("America/New_York"))


def fetch_schedule(team_id, date_str):
    r = requests.get(
        "https://statsapi.mlb.com/api/v1/schedule",
        params={"sportId": 1, "teamId": team_id, "date": date_str, "hydrate": "linescore"},
        timeout=10,
    )
    r.raise_for_status()
    dates = r.json().get("dates", [])
    return dates[0].get("games", []) if dates else []


def fetch_record(team_id, season):
    r = requests.get(
        "https://statsapi.mlb.com/api/v1/standings",
        params={"leagueId": "103,104", "season": season, "standingsTypes": "regularSeason"},
        timeout=10,
    )
    r.raise_for_status()
    for division in r.json().get("records", []):
        for entry in division.get("teamRecords", []):
            if entry["team"]["id"] == team_id:
                return entry["wins"], entry["losses"]
    return None, None


def opponent_info(game, team_id):
    home = game["teams"]["home"]
    away = game["teams"]["away"]
    is_home = home["team"]["id"] == team_id
    opp = away["team"]["name"] if is_home else home["team"]["name"]
    return opp.split()[-1], "vs" if is_home else "@"


def game_time_et(game):
    utc_str = game.get("gameDate", "")
    if not utc_str:
        return "TBD"
    dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
    return dt.astimezone(pytz.timezone("America/New_York")).strftime("%-I:%M %p ET")


def build_team_message(team_id, yesterday_str, today_str, season):
    name = TEAM_NAMES[team_id]
    wins, losses = fetch_record(team_id, season)
    record = f"{wins}-{losses}" if wins is not None else "?-?"

    # Yesterday
    yesterday_games = fetch_schedule(team_id, yesterday_str)
    if yesterday_games:
        game = yesterday_games[0]
        status = game.get("status", {}).get("detailedState", "")
        if status in ("Final", "Game Over"):
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            my_side = home if home["team"]["id"] == team_id else away
            opp_side = away if home["team"]["id"] == team_id else home
            opp_name = opp_side["team"]["name"].split()[-1]
            outcome = "Beat" if my_side.get("isWinner") else "Lost to"
            result = f"{outcome} the {opp_name} {my_side['score']}-{opp_side['score']}"
        elif "Postponed" in status:
            result = "Game postponed"
        else:
            result = f"Game {status.lower()}"
    else:
        result = "Off day"

    # Today
    today_games = fetch_schedule(team_id, today_str)
    if today_games:
        game = today_games[0]
        opp, prep = opponent_info(game, team_id)
        today = f"Play tonight {prep} {opp} @ {game_time_et(game)}"
    else:
        today = "Off today"

    return f"{name}: {result} ({record}). {today}."


def main():
    now = get_eastern_now()
    today_str = now.strftime("%Y-%m-%d")
    yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    season = now.year

    mets = build_team_message(METS_ID, yesterday_str, today_str, season)
    guardians = build_team_message(GUARDIANS_ID, yesterday_str, today_str, season)
    message = f"{mets}\n{guardians}"

    requests.post(os.environ["DISCORD_WEBHOOK_URL"], json={"content": message}, timeout=10).raise_for_status()
    print(message)


if __name__ == "__main__":
    main()
