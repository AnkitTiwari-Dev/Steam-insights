import csv
import time
from datetime import datetime
import requests
from main import lookup_ITAD_id, get_history

paid_games = []
page = 0
while len(paid_games) < 5000:
    response = requests.get("https://steamspy.com/api.php", params={"request": "all", "page": page})
    response.raise_for_status()
    data = response.json()
    if not data:
        break
    paid_games.extend([game["appid"] for game in data.values() if game["price"] != "0"])
    print(f"Page {page}: total paid appids so far = {len(paid_games)}")
    page += 1
    time.sleep(1)  # SteamSpy asks for at least 1 request per second
paid_games = paid_games[:5000]
print(paid_games)

with open("sale_events.csv","w",newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["app_id", "shop_id", "timestamp", "cut", "regular_price"])
    i = 0
    for app_id in paid_games:
        try:
            itad_id = lookup_ITAD_id(app_id)
            history = get_history(itad_id, since="2019-01-01T00:00:00Z")
            for event in history:
                writer.writerow([
                    app_id,
                    event["shop"]["id"],
                    event["timestamp"],
                    event["deal"]["cut"],
                    event["deal"]["regular"]["amount"]
                ])
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
            print(f"Processed {i}/{len(paid_games)}")
        i += 1
        time.sleep(0.35)