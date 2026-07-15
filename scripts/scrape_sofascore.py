"""Scrape season-average match ratings from Sofascore for a set of top leagues.

The Sofascore API blocks requests with an unusual TLS fingerprint (plain
`requests` gets a 403 even with browser-like headers), so this uses
`curl_cffi` with Chrome TLS/JA3 impersonation, which is accepted (verified:
200 OK on `api.sofascore.com`).

For each league (same set as scripts/scrape_transfermarkt.py) we take the
most recently *completed* season, list its teams, list each team's squad,
and pull each player's season-average rating / appearances / minutes played.

Output: data/raw/sofascore_ratings.csv
"""

import csv
import os
import time

from curl_cffi import requests as creq

BASE = "https://api.sofascore.com/api/v1"
IMPERSONATE = "chrome124"
SLEEP = 0.15

# tournament id -> league name (matches scrape_transfermarkt.py's LEAGUES where possible)
LEAGUES = {
    17: "Premier League",
    8: "LaLiga",
    23: "Serie A",
    35: "Bundesliga",
    34: "Ligue 1",
    238: "Liga Portugal",
    37: "Eredivisie",
    38: "Jupiler Pro League",
}

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
OUT_PATH = os.path.join(RAW_DIR, "sofascore_ratings.csv")


def get_json(url):
    r = creq.get(url, impersonate=IMPERSONATE, timeout=20)
    r.raise_for_status()
    return r.json()


def latest_completed_season(tournament_id):
    """Pick the most recent season that isn't the just-started current one."""
    data = get_json(f"{BASE}/unique-tournament/{tournament_id}/seasons")
    seasons = data["seasons"]
    # seasons are newest-first; skip the first if it looks brand new (few/no games yet)
    for s in seasons:
        try:
            standings = get_json(
                f"{BASE}/unique-tournament/{tournament_id}/season/{s['id']}/standings/total"
            )
            rows = standings["standings"][0]["rows"]
            if rows and rows[0]["matches"] >= 20:
                return s["id"], s["name"], rows
        except Exception:
            continue
    return None, None, []


def team_players(team_id):
    data = get_json(f"{BASE}/team/{team_id}/players")
    return [p["player"] for p in data.get("players", [])]


def player_season_stats(player_id, tournament_id, season_id):
    try:
        data = get_json(
            f"{BASE}/player/{player_id}/unique-tournament/{tournament_id}"
            f"/season/{season_id}/statistics/overall"
        )
    except Exception:
        return None
    stats = data.get("statistics")
    if not stats:
        return None
    return {
        "rating": stats.get("rating"),
        "appearances": stats.get("appearances"),
        "minutesPlayed": stats.get("minutesPlayed"),
    }


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    fieldnames = [
        "sofascore_id",
        "name",
        "league",
        "team",
        "position_ss",
        "height_ss",
        "date_of_birth_ts",
        "season_name",
        "rating",
        "appearances",
        "minutes_played",
    ]

    seen_players = set()
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for tid, league_name in LEAGUES.items():
            season_id, season_name, rows = latest_completed_season(tid)
            if season_id is None:
                print(f"skip {league_name}: no completed season found")
                continue
            print(f"{league_name}: season {season_name} ({season_id}), {len(rows)} teams")

            for row in rows:
                team = row["team"]
                try:
                    players = team_players(team["id"])
                except Exception as e:
                    print(f"  failed team players {team['name']}: {e}")
                    continue
                time.sleep(SLEEP)

                n_written = 0
                for p in players:
                    pid = p["id"]
                    if (pid, tid, season_id) in seen_players:
                        continue
                    seen_players.add((pid, tid, season_id))

                    stats = player_season_stats(pid, tid, season_id)
                    time.sleep(SLEEP)
                    if not stats or not stats.get("rating"):
                        continue

                    writer.writerow(
                        {
                            "sofascore_id": pid,
                            "name": p.get("name"),
                            "league": league_name,
                            "team": team["name"],
                            "position_ss": p.get("position"),
                            "height_ss": p.get("height"),
                            "date_of_birth_ts": p.get("dateOfBirthTimestamp"),
                            "season_name": season_name,
                            "rating": stats.get("rating"),
                            "appearances": stats.get("appearances"),
                            "minutes_played": stats.get("minutesPlayed"),
                        }
                    )
                    n_written += 1
                f.flush()
                print(f"  {team['name']}: {n_written} rated players")

    print("wrote", OUT_PATH)


if __name__ == "__main__":
    main()
