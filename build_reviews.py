import pandas as pd
import time
import requests


def fetch_reviews_for_games(app_id, max_reviews=100):
    collected = []
    cursor = "*"

    while len(collected) < max_reviews:
        url = f"https://store.steampowered.com/appreviews/{app_id}?json=1"
        params = {
            "filter": "all",
            "num_per_page": 100,
            "cursor": cursor
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        reviews = data["reviews"]
        new_cursor = data["cursor"]

        for review in reviews:
            collected.append({
                "app_id": app_id,
                "review": review["review"],
                "label": review["voted_up"],
                "playtime": review["author"]["playtime_forever"]
            })

        if new_cursor == cursor or not reviews:
            break
        cursor = new_cursor

    return collected[:max_reviews]  # in case the last page pushed past your cap


if __name__ == "__main__":
    app_ids = pd.read_csv("training_features.csv")["app_id"].unique().tolist()

    is_first_game = True
    for i, app_id in enumerate(app_ids):
        try:
            reviews = fetch_reviews_for_games(app_id)
            if reviews:
                df = pd.DataFrame(reviews)
                df.to_csv("review_corpus.csv", mode="a", header=is_first_game, index=False)
                is_first_game = False
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait = int(e.response.headers.get("Retry-After", 5))
                print(f"Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"Skipped {app_id}: {e}")
        except Exception as e:
            print(f"Skipped {app_id}: {e}")

        if i % 100 == 0:
            print(f"Processed {i}/{len(app_ids)}")
        time.sleep(0.35)