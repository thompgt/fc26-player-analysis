# EA FC 26 Player Analysis

A deep-dive data science project on EA Sports FC 26 player ratings: demographics,
how well FC ratings proxy real-world ability (validated against Sofascore match
ratings and Transfermarkt market values), player clustering/archetypes, and a
handful of creative extras (value prediction, aging curves, moneyball-style
undervalued player search).

## Data sources

- **EA FC 26 attributes**: [`rovnez/fc-26-fifa-26-player-data`](https://www.kaggle.com/datasets/rovnez/fc-26-fifa-26-player-data)
  on Kaggle (sofifa-schema export, ~18.4k players). `sofifa.com` itself sits behind a
  Cloudflare JS challenge that blocks scripted access, so this pre-scraped,
  CC-BY-licensed dataset is used as the FC26 source of truth instead of scraping
  sofifa directly.
- **Sofascore**: season average match ratings pulled from the (unofficial) Sofascore
  API, `scripts/scrape_sofascore.py`.
- **Transfermarkt**: market values scraped from squad/market-value pages,
  `scripts/scrape_transfermarkt.py`.

## Project structure

```
scripts/                  data acquisition + processing pipeline
  fetch_fc26.py            downloads the FC26 Kaggle dataset
  scrape_transfermarkt.py  scrapes market values per league/club
  scrape_sofascore.py      scrapes season average ratings per league/club
  build_dataset.py         fuzzy-matches the three sources into one player table
data/
  raw/                     untracked, gitignored (regenerate via scripts/)
  processed/               small merged/cleaned CSVs, tracked in git
notebooks/
  01_demographics.ipynb        who plays: age, nationality, body type, position, league
  02_rating_validation.ipynb   FC ratings vs Sofascore/Transfermarkt ground truth
  03_clustering.ipynb          attribute-based clustering & player archetypes
  04_extras.ipynb              value modeling, aging curves, undervalued players
```

## Reproducing

```
pip install -r requirements.txt
python scripts/fetch_fc26.py
python scripts/scrape_transfermarkt.py
python scripts/scrape_sofascore.py
python scripts/build_dataset.py
jupyter notebook
```

Kaggle API credentials must be set via `KAGGLE_USERNAME`/`KAGGLE_KEY` env vars
(or `~/.kaggle/kaggle.json`) to run `fetch_fc26.py`.
