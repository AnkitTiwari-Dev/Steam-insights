import logging
import os
from datetime import datetime, timedelta
from agent import run_agent
import joblib
import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import SessionLocal
from features import days_to_nearest_sale, steam_sale_dates
from models import Game, Rating

logger = logging.getLogger("steam_insights")

model = joblib.load("sale_prediction_model.joblib")
load_dotenv()
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
DEAL_API = os.getenv("DEAL_API")
REQUEST_TIMEOUT = 10  # seconds; stops a slow upstream API from hanging a request

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://steam-insights.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- helpers ----------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_fresh(timestamp, hours=24):
    """True if timestamp is within `hours` of now. Works for naive and tz-aware values."""
    if timestamp is None:
        return False
    now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
    return now - timestamp < timedelta(hours=hours)


def valid_steam_id(steam_id: str) -> bool:
    return steam_id.isdigit() and len(steam_id) == 17


def average_gap_days(hist):
    """Average days between consecutive sales (hist is newest-first). None if < 2 sales."""
    if len(hist) < 2:
        return None
    total = timedelta()
    for newer, older in zip(hist, hist[1:]):
        total += datetime.fromisoformat(newer["timestamp"]) - datetime.fromisoformat(older["timestamp"])
    return total.total_seconds() / 86400 / (len(hist) - 1)


# ---------- Steam ----------

def get_owned(steam_id):
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
    params = {
        "key": STEAM_API_KEY,
        "steamid": steam_id,
        "include_appinfo": True,
        "include_played_free_games": True,
    }
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    # Private profiles come back as {"response": {}} with no "games" key
    return response.json().get("response", {}).get("games")


@app.get("/library/{steam_id}")
def get_games(steam_id: str):
    if not valid_steam_id(steam_id):
        raise HTTPException(status_code=400, detail="Steam ID must be 17 digits")
    try:
        games = get_owned(steam_id)
    except requests.RequestException:
        logger.exception("library fetch failed for %s", steam_id)
        raise HTTPException(status_code=502, detail="Steam request failed, please try again")
    if not games:
        raise HTTPException(
            status_code=404,
            detail="No games found. Check the Steam ID and that game details are public",
        )
    sort_games = sorted(games, key=lambda g: g.get("playtime_forever", 0), reverse=True)
    return {"steam_id": steam_id, "games": sort_games}


@app.get("/reviews/{app_id}")
def get_reviews(app_id: int):
    try:
        url = f"https://store.steampowered.com/appreviews/{app_id}?json=1"
        params = {"filter": "all", "num_per_page": 100}
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        rev_lst = response.json().get("reviews", [])
    except (requests.RequestException, ValueError):
        logger.exception("reviews fetch failed for %s", app_id)
        raise HTTPException(status_code=502, detail="Could not fetch reviews")
    reviews = [r for r in rev_lst if r.get("author", {}).get("playtime_forever", 0) > 1800]
    return {"app_id": app_id, "reviews": reviews}


@app.get("/review_stats/{app_id}")
def get_review_stats(app_id: int, db: Session = Depends(get_db)):
    # Cache hit: same keys as a fresh response, with None where we don't store the detail
    cached_game = db.query(Game).filter(Game.app_id == app_id).first()
    if cached_game and is_fresh(cached_game.review_checked):
        return {
            "app_id": app_id,
            "overall_percent": cached_game.review_overall_percent,
            "total_rev": None,
            "by_play": None,
        }

    try:
        url = f"https://store.steampowered.com/appreviews/{app_id}?json=1"
        params = {"filter": "recent", "num_per_page": 100}
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        rev_lst = response.json().get("reviews", [])
    except (requests.RequestException, ValueError):
        logger.exception("review_stats failed for %s", app_id)
        raise HTTPException(status_code=502, detail="Could not fetch reviews")

    sections = {"<2": [0, 0], "2-10": [0, 0], "10-30": [0, 0], "30-100": [0, 0], "100+": [0, 0]}
    for review in rev_lst:
        playtime = review["author"]["playtime_forever"] / 60
        if playtime < 2:
            key = "<2"
        elif playtime < 10:
            key = "2-10"
        elif playtime < 30:
            key = "10-30"
        elif playtime < 100:
            key = "30-100"
        else:
            key = "100+"
        sections[key][0] += 1
        if review["voted_up"]:
            sections[key][1] += 1

    output = {}
    for section, (total, recommended) in sections.items():
        output[section] = round((recommended / total) * 100, 2) if total > 0 else None
    total_rev = len(rev_lst)
    total_recc = sum(1 for r in rev_lst if r["voted_up"])
    overall_percent = round((total_recc / total_rev) * 100, 2) if total_rev > 0 else None

    # A cache-write failure should never break the response
    try:
        if cached_game:
            cached_game.review_overall_percent = overall_percent
            cached_game.review_checked = datetime.now()
        else:
            db.add(Game(app_id=app_id, review_overall_percent=overall_percent, review_checked=datetime.now()))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("could not cache review stats for %s", app_id)

    return {
        "app_id": app_id,
        "overall_percent": overall_percent,
        "total_rev": total_rev,
        "by_play": output,
    }


# ---------- IsThereAnyDeal ----------

def lookup_ITAD_id(app_id: int):
    """Returns the ITAD id, or None if ITAD doesn't know this game."""
    url = "https://api.isthereanydeal.com/games/lookup/v1"
    params = {"key": DEAL_API, "appid": app_id}
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    game = data.get("game") if data.get("found", True) else None
    return game["id"] if game else None


def get_history(itad_id: str, since=None):
    url = "https://api.isthereanydeal.com/games/history/v2"
    params = {"key": DEAL_API, "id": itad_id, "shops": 61}
    if since:
        params["since"] = since
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    history = response.json()
    sales = [cut for cut in history if cut["deal"]["cut"] > 0]
    sales.sort(key=lambda x: datetime.fromisoformat(x["timestamp"]), reverse=True)
    return sales


def get_current_price(itad_id: str):
    """Current best price, or None if there is no active deal data."""
    url = "https://api.isthereanydeal.com/games/prices/v3"
    params = {"key": DEAL_API, "deals": True, "vouchers": True}
    response = requests.post(url, params=params, json=[itad_id], timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    sale = response.json()
    if not sale or not sale[0].get("deals"):
        return None
    return sale[0]["deals"][0]["price"]["amount"]


@app.get("/last_sale/{app_id}")
def get_last_sale(app_id: int, db: Session = Depends(get_db)):
    # Always returns {"app_id", "prices": number|None, "next_sale": datetime|None},
    # for both cache hits and fresh lookups (previously these had different shapes).
    cached_game = db.query(Game).filter(Game.app_id == app_id).first()
    if cached_game and is_fresh(cached_game.last_checked):
        return {"app_id": app_id, "prices": cached_game.current_price, "next_sale": cached_game.last_sale_date}

    try:
        itad_id = lookup_ITAD_id(app_id)
        current_price = None
        next_sale = None
        gap_days = None
        if itad_id:
            current_price = get_current_price(itad_id)
            gap_days = average_gap_days(get_history(itad_id))
            if gap_days is not None:
                next_sale = datetime.now() + timedelta(days=gap_days)
    except Exception:
        logger.exception("last_sale failed for %s", app_id)
        raise HTTPException(status_code=502, detail="Could not fetch price data")

    # Cache "no data" results too, so unsupported games don't hit ITAD on every page load
    try:
        if cached_game:
            cached_game.itad_id = itad_id
            cached_game.last_checked = datetime.now()
            cached_game.current_price = current_price
            cached_game.average_gap_days = gap_days
            cached_game.last_sale_date = next_sale
        else:
            db.add(Game(
                app_id=app_id,
                itad_id=itad_id,
                last_checked=datetime.now(),
                current_price=current_price,
                average_gap_days=gap_days,
                last_sale_date=next_sale,
            ))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("could not cache last_sale for %s", app_id)

    return {"app_id": app_id, "prices": current_price, "next_sale": next_sale}


def compute_features(app_id: int):
    """Returns the model's feature list, or None if there isn't enough sale history."""
    itad_id = lookup_ITAD_id(app_id)
    if itad_id is None:
        return None
    hist = get_history(itad_id, since="2019-01-01T00:00:00Z")
    if len(hist) < 2:
        return None

    num_sales = len(hist)
    avg_cut = sum(event["deal"]["cut"] for event in hist) / num_sales
    avg_gap_days = average_gap_days(hist)

    most_recent_timestamp = datetime.fromisoformat(hist[0]["timestamp"])
    days_since_last_sale = (
        datetime.now(most_recent_timestamp.tzinfo) - most_recent_timestamp
    ).total_seconds() / 86400

    regular_price = hist[0]["deal"]["regular"]["amount"]
    today = pd.Timestamp(datetime.now(), tz="UTC")
    days_to_next_sale = days_to_nearest_sale(today, steam_sale_dates)
    return [num_sales, avg_cut, avg_gap_days, regular_price, days_since_last_sale, days_to_next_sale]


@app.get("/predict/{app_id}")
def predict(app_id: int):
    try:
        features = compute_features(app_id)
        if features is None:
            return {"app_id": app_id, "sale_probability": None}  # not enough history
        sale_prob = float(model.predict_proba([features])[0][1])
    except requests.RequestException:
        logger.exception("predict upstream failure for %s", app_id)
        raise HTTPException(status_code=502, detail="Could not fetch sale data")
    except Exception:
        logger.exception("predict failed for %s", app_id)
        raise HTTPException(status_code=500, detail="Could not compute prediction")
    return {"app_id": app_id, "sale_probability": sale_prob}


@app.get("/history/{app_id}")
def get_price_history(app_id: int):
    try:
        itad_id = lookup_ITAD_id(app_id)
        if itad_id is None:
            return []
        hist = get_history(itad_id, since="2019-01-01T00:00:00Z")
    except Exception:
        logger.exception("history failed for %s", app_id)
        raise HTTPException(status_code=502, detail="Could not fetch price history")
    return [
        {
            "timestamp": event["timestamp"],
            "cut": event["deal"]["cut"],
            "regular_price": event["deal"]["regular"]["amount"],
        }
        for event in hist
    ]


# --- Personal rating (want/own/played-style) ---

class RatingInput(BaseModel):
    app_id: int
    steam_id: str
    status: str
    score: int | None = None


@app.post("/rating")
def set_rating(payload: RatingInput, db: Session = Depends(get_db)):
    if payload.status not in {"skip it", "timepass", "go for it", "perfection"}:
        raise HTTPException(status_code=400, detail="invalid status")
    if payload.score is not None and not (1 <= payload.score <= 10):
        raise HTTPException(status_code=400, detail="score must be between 1 and 10")

    existing = (
        db.query(Rating)
        .filter(Rating.app_id == payload.app_id, Rating.steam_id == payload.steam_id)
        .first()
    )

    if existing:
        existing.status = payload.status
        existing.score = payload.score
        db.commit()
        db.refresh(existing)
        return existing

    new_rating = Rating(
        app_id=payload.app_id,
        steam_id=payload.steam_id,
        status=payload.status,
        score=payload.score,
    )
    db.add(new_rating)
    db.commit()
    db.refresh(new_rating)
    return new_rating


@app.get("/ratings/{steam_id}")
def get_ratings(steam_id: str, db: Session = Depends(get_db)):
    ratings = db.query(Rating).filter(Rating.steam_id == steam_id).all()
    return {r.app_id: {"status": r.status, "score": r.score} for r in ratings}


# --- Community-wide rating aggregate (Moctale meter) ---

ALL_STATUSES = ["skip it", "timepass", "go for it", "perfection"]


@app.get("/community_rating/{app_id}")
def get_community_rating(app_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(Rating.status, func.count(Rating.id))
        .filter(Rating.app_id == app_id)
        .group_by(Rating.status)
        .all()
    )
    counts = {status: 0 for status in ALL_STATUSES}
    for status, count in rows:
        if status in counts:
            counts[status] = count

    return {
        "app_id": app_id,
        "total_votes": sum(counts.values()),
        "counts": counts,
    }

from agent import run_agent

class AskInput(BaseModel):
    steam_id: str
    question: str

@app.post("/ask")
def ask(payload: AskInput):
    if not valid_steam_id(payload.steam_id):
        raise HTTPException(status_code=400, detail="Steam ID must be 17 digits")

    def library_tool(_):
        games = get_owned(payload.steam_id) or []
        games = sorted(games, key=lambda g: g.get("playtime_forever", 0), reverse=True)[:25]
        return [{"name": g["name"], "app_id": g["appid"],
                 "hours": round(g.get("playtime_forever", 0) / 60, 1)} for g in games]

    def sale_tool(args):
        app_id = int(args["app_id"])
        db = SessionLocal()
        try:
            sale = get_last_sale(app_id, db)
        finally:
            db.close()
        pred = predict(app_id)
        return {"sale_probability": pred["sale_probability"],
                "current_price": sale["prices"], "next_sale": sale["next_sale"]}

    def review_tool(args):
        db = SessionLocal()
        try:
            r = get_review_stats(int(args["app_id"]), db)
        finally:
            db.close()
        return {"percent_positive": r["overall_percent"]}

    return run_agent(payload.question, {
        "get_library": library_tool,
        "get_sale_prediction": sale_tool,
        "get_review_summary": review_tool,
    })

