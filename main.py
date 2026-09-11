import requests
import os
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from datetime import datetime,timedelta

app = FastAPI()
load_dotenv()
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
DEAL_API = os.getenv("DEAL_API")
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
@app.get("/library/{steam_id}")
def get_games(steam_id:str):
   try:
    games = get_owned(steam_id)
   except:
      raise HTTPException(status_code=400,detail="Could not fetch games, check steam ID and profile privacy")
   sort_games = sorted(games, key= lambda g: g["playtime_forever"],reverse=True)
   names = [game["name"] for game in sort_games]
   return{"steam_id":steam_id, "games" : sort_games}

@app.get("/reviews/{app_id}")
def get_reviews(app_id:int):
   try:
      url = f"https://store.steampowered.com/appreviews/{app_id}?json=1"
      params = {
        "filter" : "all",
        "num_per_page" : 100
      }
      response = requests.get(url,params=params)
      response.raise_for_status()
      rev_lst = response.json()["reviews"]
   except:
      raise HTTPException(status_code=400, detail="Could not fetch reviews, check app ID")
   reviews = [review for review in rev_lst if review["author"]["playtime_forever"] > 1800]
   return{"app_id":app_id,"reviews":reviews}

@app.get("/last_sale/{app_id}")
def get_last_sale(app_id:int):
    try:
        itad_id = lookup_ITAD_id(app_id)
        url = f"https://api.isthereanydeal.com/games/prices/v3"
        params = {
           "key" :DEAL_API,
           "deals":True,
           "vouchers":True
       }
        response = requests.post(url,params=params,json=[itad_id])
        response.raise_for_status()
        sale = response.json()
        hist = get_history(itad_id)
        average_gap = timedelta()
        for i in range(len(hist) - 1):
           sale_gap = datetime.fromisoformat(hist[i]["timestamp"]) - datetime.fromisoformat(hist[i + 1]["timestamp"])
           average_gap += sale_gap
        average_gap /= (len(hist) - 1)
        next_sale = datetime.now() + average_gap 
    except Exception as e:
       print(e)
       raise HTTPException(status_code=400, detail="Could not fetch price, check app ID")
    return{"app_id":app_id,"prices":sale,"next_sale":next_sale}

def lookup_ITAD_id(app_id:int):
   url = f"https://api.isthereanydeal.com/games/lookup/v1"
   params = {
      "key":DEAL_API,
      "appid":app_id
   }
   response = requests.get(url,params=params)
   response.raise_for_status()
   return response.json()["game"]["id"]

def get_history(Itad_id:str):
   url = f"https://api.isthereanydeal.com/games/history/v2"
   params = {
      "key":DEAL_API,
      "id":Itad_id,
      "shops":61
   }
   response = requests.get(url,params=params)
   response.raise_for_status()
   cuts = response.json()
   return [cut for cut in cuts if cut["deal"]["cut"] > 0]

if __name__ == "__main__":
    print(get_history(lookup_ITAD_id(1091500)))