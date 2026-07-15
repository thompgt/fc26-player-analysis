"""Scrape player market values from Transfermarkt for a set of top leagues.

transfermarkt.com serves plain HTML with no bot-blocking observed (verified:
plain `requests` gets a normal 200), so this uses requests + BeautifulSoup
with a polite delay between requests.

For each league we list its clubs, then for each club we scrape the squad
("Kader") page, which includes market value, age, height, foot, nationality,
and contract details per player.

Output: data/raw/transfermarkt_players.csv
"""

import csv
import os
import re
import time

import requests
from bs4 import BeautifulSoup

BASE = "https://www.transfermarkt.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
SEASON_ID = "2026"
SLEEP = 1.2

LEAGUES = {
    "GB1": "Premier League",
    "ES1": "LaLiga",
    "IT1": "Serie A",
    "L1": "Bundesliga",
    "FR1": "Ligue 1",
    "PO1": "Liga Portugal",
    "NL1": "Eredivisie",
    "BE1": "Jupiler Pro League",
}

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
OUT_PATH = os.path.join(RAW_DIR, "transfermarkt_players.csv")


def get_soup(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def league_clubs(league_code):
    url = f"{BASE}/wettbewerb/startseite/wettbewerb/{league_code}/saison_id/{SEASON_ID}"
    soup = get_soup(url)
    clubs = {}
    for a in soup.select("table.items td.hauptlink a[href*='/startseite/verein/']"):
        href = a.get("href", "")
        m = re.match(r"/([^/]+)/startseite/verein/(\d+)", href)
        if m:
            slug, cid = m.groups()
            clubs[cid] = slug
    return clubs


def parse_market_value(text):
    text = text.strip().replace("€", "").replace(",", ".")
    if not text or text == "-":
        return None
    mult = 1
    if text.endswith("bn"):
        mult = 1_000_000_000
        text = text[:-2]
    elif text.endswith("m"):
        mult = 1_000_000
        text = text[:-1]
    elif text.endswith("k"):
        mult = 1_000
        text = text[:-1]
    try:
        return float(text) * mult
    except ValueError:
        return None


def parse_age(dob_text):
    m = re.search(r"\((\d+)\)", dob_text)
    return int(m.group(1)) if m else None


def parse_height(text):
    text = text.strip().replace("m", "").replace(",", ".")
    try:
        return float(text) * 100  # cm
    except ValueError:
        return None


def club_squad(league_name, club_slug, club_id):
    url = f"{BASE}/{club_slug}/kader/verein/{club_id}/saison_id/{SEASON_ID}/plus/1"
    soup = get_soup(url)
    table = soup.select_one("table.items")
    if table is None:
        return []
    rows = table.select("tbody > tr")
    players = []
    for row in rows:
        tds = row.find_all("td", recursive=False)
        if len(tds) < 9:
            continue
        name_link = row.select_one("td.hauptlink a")
        if name_link is None:
            continue
        name = name_link.get_text(strip=True)
        profile_href = name_link.get("href", "")
        pid_m = re.search(r"/spieler/(\d+)", profile_href)
        player_id = pid_m.group(1) if pid_m else None

        position = tds[1].get_text(" ", strip=True).replace(name, "").strip()
        dob_text = tds[2].get_text(" ", strip=True)
        age = parse_age(dob_text)

        flags = row.select("td img.flaggenrahmen")
        nationalities = [f.get("title") for f in flags if f.get("title")]

        height_cm = parse_height(tds[4].get_text(strip=True))
        foot = tds[5].get_text(strip=True)
        contract_until = tds[8].get_text(strip=True)
        market_value = parse_market_value(tds[9].get_text(strip=True)) if len(tds) > 9 else None

        players.append(
            {
                "transfermarkt_id": player_id,
                "name": name,
                "league": league_name,
                "club": club_slug,
                "position_tm": position,
                "age_tm": age,
                "nationality_tm": nationalities[0] if nationalities else None,
                "nationality2_tm": nationalities[1] if len(nationalities) > 1 else None,
                "height_cm_tm": height_cm,
                "foot_tm": foot,
                "contract_until": contract_until,
                "market_value_eur": market_value,
            }
        )
    return players


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    fieldnames = [
        "transfermarkt_id",
        "name",
        "league",
        "club",
        "position_tm",
        "age_tm",
        "nationality_tm",
        "nationality2_tm",
        "height_cm_tm",
        "foot_tm",
        "contract_until",
        "market_value_eur",
    ]
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for code, league_name in LEAGUES.items():
            try:
                clubs = league_clubs(code)
            except Exception as e:
                print(f"failed to list clubs for {league_name}: {e}")
                continue
            print(f"{league_name}: {len(clubs)} clubs")
            time.sleep(SLEEP)

            for cid, slug in clubs.items():
                try:
                    players = club_squad(league_name, slug, cid)
                except Exception as e:
                    print(f"  failed {slug}: {e}")
                    continue
                for p in players:
                    writer.writerow(p)
                f.flush()
                print(f"  {slug}: {len(players)} players")
                time.sleep(SLEEP)

    print("wrote", OUT_PATH)


if __name__ == "__main__":
    main()
