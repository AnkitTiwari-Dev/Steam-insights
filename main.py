import requests
import os
import pandas as pd
from fastapi import FastAPI, HTTPException, Depends
from dotenv import load_dotenv
from datetime import datetime,timedelta
from database import SessionLocal
from sqlalchemy.orm import Session
from models import Game
from features import days_to_nearest_sale, steam_sale_dates
import joblib
from fastapi.middleware.cors import CORSMiddleware

model = joblib.load("sale_prediction_model.joblib")  
load_dotenv()
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
DEAL_API = os.getenv("DEAL_API")
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
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
def get_db():
   db = SessionLocal()
   try:
      yield db
   finally:
      db.close()

@app.get("/review_stats/{app_id}")
def get_review_stats(app_id:int):
   try:
      url = f"https://store.steampowered.com/appreviews/{app_id}?json=1"
      params = {
        "filter" : "recent",
        "num_per_page" : 100
      }
      response = requests.get(url,params=params)
      response.raise_for_status()
      rev_lst = response.json()["reviews"]
   except:
      raise HTTPException(status_code=400, detail="Could not fetch reviews, check app ID")
   sections = {"<2":[0,0],"2-10":[0,0],"10-30":[0,0],"30-100":[0,0],"100+":[0,0]}
   key = ""
   for review in rev_lst:
      playtime = review["author"]["playtime_forever"]/60
      if playtime < 2:
         key = "<2"
      elif 2 <= playtime < 10:
         key = "2-10"
      elif 10 <= playtime < 30:
         key = "10-30"
      elif 30 <= playtime < 100:
         key = "30-100"
      else:
         key = "100+"
      sections[key][0] += 1
      if review["voted_up"]:
         sections[key][1] +=1

   output = {}
   for section, (total,recommended) in sections.items():
      output[section] = round((recommended/total) * 100, 2) if total > 0 else None
   total_rev = len(rev_lst)
   total_recc = sum(1 for r in rev_lst if r["voted_up"])
   overall_percent = round((total_recc/total_rev) * 100, 2) if total_rev > 0 else None

   return{
      "app_id":app_id,
      "overall_percent":overall_percent,
      "total_rev":total_rev,
      "by_play":output
   }
   

@app.get("/last_sale/{app_id}")
def get_last_sale(app_id:int,db : Session = Depends(get_db)):
    cached_game = db.query(Game).filter(Game.app_id == app_id).first()
    if cached_game and (datetime.now() - cached_game.last_checked < timedelta(hours=24)):
       print("Using cache")
       return{"app_id":app_id,"prices":cached_game.current_price,"next_sale":cached_game.last_sale_date}
    try:
        print("retrieving")
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
        current_price = sale[0]["deals"][0]["price"]["amount"]
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
    new_game = Game(app_id=app_id,
                    itad_id=itad_id,
                    last_checked=datetime.now(),
                    current_price=current_price,
                    average_gap_days=average_gap.total_seconds()/86400,
                    last_sale_date=next_sale)
    db.add(new_game)
    db.commit()
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

def get_history(Itad_id:str,since=None):
   url = f"https://api.isthereanydeal.com/games/history/v2"
   params = {
      "key":DEAL_API,
      "id":Itad_id,
      "shops":61,
   }
   if since:
      params["since"] = since
   response = requests.get(url,params=params)
   response.raise_for_status()
   history = response.json()
   sales = [cut for cut in history if cut["deal"]["cut"] > 0]
   sales.sort(key= lambda x: datetime.fromisoformat(x["timestamp"]),reverse=True)
   return sales
def compute_features(app_id:int):
   itad_id = lookup_ITAD_id(app_id)
   hist = get_history(itad_id, since="2019-01-01T00:00:00Z")
   num_sales = len(hist)
   cuts = [event["deal"]["cut"] for event in hist]
   avg_cut = sum(cuts)/len(cuts)
   average_gap = timedelta()
   if len(hist) < 2:
      raise ValueError("Not enough history to compute prediction")
   for i in range(len(hist) - 1):
      gap = datetime.fromisoformat(hist[i]["timestamp"]) - datetime.fromisoformat(hist[i + 1]["timestamp"])
      average_gap += gap
   avg_gap_days = average_gap.total_seconds() / 86400 / (len(hist) - 1)

   most_recent_timestamp = datetime.fromisoformat(hist[0]["timestamp"])
   days_since_last_sale = (datetime.now(most_recent_timestamp.tzinfo) - most_recent_timestamp).total_seconds() / 86400

   regular_price = hist[0]["deal"]["regular"]["amount"]
   today = pd.Timestamp(datetime.now(), tz="UTC")
   days_to_next_sale = days_to_nearest_sale(today, steam_sale_dates)
   return [num_sales, avg_cut, avg_gap_days, regular_price, days_since_last_sale, days_to_next_sale]
 
@app.get("/predict/{app_id}")
def predict(app_id:int):
   try:
      
      features = compute_features(app_id)
      sale_prob = model.predict_proba([features])[0][1]
   except Exception as e:
      print(e)
      raise HTTPException(status_code=400, detail="Could not compute prediction")
   return {"app_id": app_id, "sale_probability": sale_prob}

@app.get("/history/{app_id}")
def get_price_history(app_id: int):
    try:
        itad_id = lookup_ITAD_id(app_id)
        hist = get_history(itad_id, since="2019-01-01T00:00:00Z")
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Could not fetch price history")
    return [
        {
            "timestamp": event["timestamp"],
            "cut": event["deal"]["cut"],
            "regular_price": event["deal"]["regular"]["amount"]
        }
        for event in hist
    ]



if __name__ == "__main__":
    print(lookup_ITAD_id(1687950))
    print(get_history("018d937f-4adb-73a6-a9e5-94ff62f6265b", since="2019-01-01T00:00:00Z"))