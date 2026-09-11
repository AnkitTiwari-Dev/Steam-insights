import os
import requests
from dotenv import load_dotenv

load_dotenv()
STEAM_ID = os.getenv("STEAM_ID")
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
def get_owned(steam_id):
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    params = {
        "key" : STEAM_API_KEY,
        "steamid" :steam_id,
        "include_appinfo" : True,
        "include_played_free_games" : True
    }
    response = requests.get(url,params=params)
    response.raise_for_status()
    return response.json()["response"]["games"]
if __name__ == "__main__":
    games = get_owned(STEAM_ID)
    for game in sorted(games, key= lambda g: g["playtime_forever"],reverse=True):
        hours = game["playtime_forever"] /60
        print(f"{game['name']} : {hours:.1f} hours")