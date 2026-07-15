"""Fuzzy-match FC26 <-> Transfermarkt <-> Sofascore into one player table.

There's no shared player ID across these three sources, so matching is done
by full name similarity (rapidfuzz), blocked by age (+/-1 year) to keep the
comparison space small and to avoid false positives between different
players who share a name.

Outputs:
  data/processed/players_fc26_clean.csv   full FC26 dataset, lightly cleaned
  data/processed/players_merged.csv       FC26 players matched to TM value / Sofascore rating
  data/processed/match_stats.json         match-rate diagnostics
"""

import json
import os
import unicodedata

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROC_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")

NAME_MATCH_THRESHOLD = 87


def normalize_name(name):
    if pd.isna(name):
        return ""
    name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return name.lower().strip()


def load_fc26():
    df = pd.read_csv(os.path.join(RAW_DIR, "FC26_20250921.csv"), low_memory=False)
    keep = [
        "player_id", "short_name", "long_name", "player_positions", "overall", "potential",
        "value_eur", "wage_eur", "age", "dob", "height_cm", "weight_kg",
        "league_name", "league_level", "club_name", "club_position",
        "nationality_name", "preferred_foot", "weak_foot", "skill_moves",
        "international_reputation", "work_rate", "body_type",
        "pace", "shooting", "passing", "dribbling", "defending", "physic",
    ]
    df = df[keep].copy()
    df["name_norm"] = df["long_name"].map(normalize_name)
    return df


def load_transfermarkt():
    df = pd.read_csv(os.path.join(RAW_DIR, "transfermarkt_players.csv"))
    df["name_norm"] = df["name"].map(normalize_name)
    return df


def load_sofascore():
    df = pd.read_csv(os.path.join(RAW_DIR, "sofascore_ratings.csv"))
    df["name_norm"] = df["name"].map(normalize_name)
    df["age_ss"] = (
        (pd.Timestamp("2026-06-01") - pd.to_datetime(df["date_of_birth_ts"], unit="s", errors="coerce"))
        .dt.days // 365
    )
    return df


def fuzzy_match(left, right, left_age_col, right_age_col, right_name_col="name_norm", age_tol=1):
    """For each row in `left`, find best-matching row index in `right`,
    restricted to candidates within `age_tol` years, above NAME_MATCH_THRESHOLD.
    Returns a Series of matched right-index (or NaN) aligned to left.index.
    """
    right_by_age = {}
    for age, sub in right.groupby(right_age_col):
        if pd.isna(age):
            continue
        right_by_age[int(age)] = sub

    matched_idx = pd.Series(index=left.index, dtype="float64")
    scores = pd.Series(index=left.index, dtype="float64")

    for age, sub_left in left.groupby(left_age_col):
        if pd.isna(age):
            continue
        age = int(age)
        candidates = pd.concat(
            [right_by_age.get(a) for a in (age - age_tol, age, age + age_tol) if a in right_by_age]
        ) if any(a in right_by_age for a in (age - age_tol, age, age + age_tol)) else None
        if candidates is None or candidates.empty:
            continue
        choices = candidates[right_name_col].tolist()
        choice_idx = candidates.index.tolist()

        for i, name in sub_left[["name_norm"]].itertuples():
            if not name:
                continue
            best = process.extractOne(name, choices, scorer=fuzz.token_sort_ratio)
            if best and best[1] >= NAME_MATCH_THRESHOLD:
                matched_idx.loc[i] = choice_idx[best[2]]
                scores.loc[i] = best[1]

    return matched_idx, scores


def main():
    os.makedirs(PROC_DIR, exist_ok=True)

    fc26 = load_fc26()
    tm = load_transfermarkt()
    ss = load_sofascore()

    fc26.to_csv(os.path.join(PROC_DIR, "players_fc26_clean.csv"), index=False)

    tm_idx, tm_scores = fuzzy_match(fc26, tm, "age", "age_tm")
    ss_idx, ss_scores = fuzzy_match(fc26, ss, "age", "age_ss")

    merged = fc26.copy()
    merged["tm_match_idx"] = tm_idx
    merged["tm_match_score"] = tm_scores
    merged["ss_match_idx"] = ss_idx
    merged["ss_match_score"] = ss_scores

    tm_lookup = tm[["market_value_eur", "position_tm", "foot_tm", "contract_until", "league"]].copy()
    tm_lookup.columns = ["market_value_eur", "position_tm", "foot_tm", "contract_until", "tm_league"]
    merged = merged.join(tm_lookup, on="tm_match_idx")

    ss_lookup = ss[["rating", "appearances", "minutes_played", "league"]].copy()
    ss_lookup.columns = ["sofascore_rating", "sofascore_appearances", "sofascore_minutes", "ss_league"]
    merged = merged.join(ss_lookup, on="ss_match_idx")

    merged = merged.drop(columns=["tm_match_idx", "ss_match_idx"])
    merged.to_csv(os.path.join(PROC_DIR, "players_merged.csv"), index=False)

    stats = {
        "fc26_players": int(len(fc26)),
        "transfermarkt_players": int(len(tm)),
        "sofascore_players": int(len(ss)),
        "matched_to_transfermarkt": int(merged["market_value_eur"].notna().sum()),
        "matched_to_sofascore": int(merged["sofascore_rating"].notna().sum()),
        "matched_to_both": int((merged["market_value_eur"].notna() & merged["sofascore_rating"].notna()).sum()),
    }
    with open(os.path.join(PROC_DIR, "match_stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
