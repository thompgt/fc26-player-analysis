"""Download the EA FC 26 player attribute dataset from Kaggle.

sofifa.com sits behind a Cloudflare JS challenge that blocks scripted
requests (verified: plain `requests` and `curl_cffi` browser-impersonation
both get a 403 "Just a moment..." challenge page), so we use a pre-scraped,
CC-BY-licensed mirror of the same data instead of scraping sofifa directly.

Source: https://www.kaggle.com/datasets/rovnez/fc-26-fifa-26-player-data
"""

import os
import zipfile

DATASET = "rovnez/fc-26-fifa-26-player-data"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(DATASET, path=RAW_DIR, unzip=False)

    zip_path = os.path.join(RAW_DIR, DATASET.split("/")[-1] + ".zip")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(RAW_DIR)
    os.remove(zip_path)

    for f in os.listdir(RAW_DIR):
        if f.endswith(".csv"):
            print("downloaded:", os.path.join(RAW_DIR, f))


if __name__ == "__main__":
    main()
