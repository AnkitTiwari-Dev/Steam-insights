import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";
import { Clock, ThumbsUp } from "lucide-react";
import "./App.css";
import RatingWidget from "./RatingWidget";

// To test against a local backend, create .env.local with:
//   VITE_API_URL=http://localhost:8000
// and restart `npm run dev`. Without it, the deployed backend is used.
const API_BASE = import.meta.env.VITE_API_URL ?? "https://playstats.onrender.com";

// How many review_stats requests run at once. Steam's store API throttles
// bursts, so keep this low.
const RECOMMEND_CONCURRENCY = 3;

// Fetch JSON from the backend. Returns null on any failure (network error,
// non-2xx status, bad JSON) so callers never receive an error body by mistake.
async function getJson(path) {
  try {
    const response = await fetch(`${API_BASE}${path}`);
    if (!response.ok) return null;
    return await response.json();
  } catch (e) {
    console.error(`Request failed: ${path}`, e);
    return null;
  }
}

// Falls back to the wide header image when Steam has no tall library art.
function coverStyle(appid) {
  const base = `https://cdn.akamai.steamstatic.com/steam/apps/${appid}`;
  return {
    backgroundImage: `url(${base}/library_600x900.jpg), url(${base}/header.jpg)`,
  };
}

function App() {
  const [user_ratings, set_user_ratings] = useState({});
  const [steam_id, set_steam_id] = useState("76561199570092491");
  const [library, set_library] = useState(null);
  const [searching, set_searching] = useState(false);
  const [search_error, set_search_error] = useState(null);
  const [selection, set_selection] = useState(null);

  // For these four: undefined = still loading, null = failed / no data.
  const [sale_info, change_sale_info] = useState(undefined);
  const [prediction, set_prediction] = useState(undefined);
  const [reviews, set_reviews] = useState(undefined);
  const [history, set_history] = useState(undefined);

  // recommend_data[appid]: undefined = loading, null = N/A, number = percent
  const [recommend_data, set_recommend_data] = useState({});

  // Load everything for the selected game. The `cancelled` flag stops a slow
  // response for a previous game from overwriting the current one.
  useEffect(() => {
    if (!selection) return;
    let cancelled = false;
    const appid = selection.appid;

    change_sale_info(undefined);
    set_prediction(undefined);
    set_reviews(undefined);
    set_history(undefined);

    getJson(`/last_sale/${appid}`).then((d) => !cancelled && change_sale_info(d));
    getJson(`/predict/${appid}`).then((d) => !cancelled && set_prediction(d));
    getJson(`/reviews/${appid}`).then((d) => !cancelled && set_reviews(d));
    getJson(`/history/${appid}`).then((d) => !cancelled && set_history(d));
    // Note: the route is /ratings/ (plural) -- the old code called /rating/ and got a 404
    getJson(`/ratings/${steam_id}`).then((d) => {
      if (!cancelled && d) set_user_ratings(d);
    });

    return () => {
      cancelled = true;
    };
  }, [selection]);

  // Load review percentages for the library, a few at a time. Results appear
  // on each card as they arrive instead of all at once at the end.
  useEffect(() => {
    if (!library?.games) return;
    let cancelled = false;
    const games = library.games;
    let index = 0;

    set_recommend_data({});

    async function worker() {
      while (!cancelled && index < games.length) {
        const game = games[index];
        index++;
        const data = await getJson(`/review_stats/${game.appid}`);
        if (cancelled) return;
        const value = data?.overall_percent ?? null;
        set_recommend_data((prev) => ({ ...prev, [game.appid]: value }));
      }
    }

    for (let i = 0; i < RECOMMEND_CONCURRENCY; i++) worker();

    return () => {
      cancelled = true;
    };
  }, [library]);

  async function lib_search() {
    set_search_error(null);
    set_searching(true);
    try {
      const response = await fetch(`${API_BASE}/library/${steam_id.trim()}`);
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        set_library(null);
        set_search_error(
          typeof data?.detail === "string"
            ? data.detail
            : "Could not load that library. Please try again."
        );
        return;
      }
      set_library(data);
    } catch (e) {
      console.error("Library search failed", e);
      set_library(null);
      set_search_error(
        "Could not reach the server. It may be waking up, so try again in a few seconds."
      );
    } finally {
      set_searching(false);
    }
  }

  const sale_text =
    sale_info === undefined
      ? "..."
      : sale_info?.next_sale
        ? new Date(sale_info.next_sale).toLocaleDateString()
        : "N/A";

  const prediction_text =
    prediction === undefined
      ? "..."
      : prediction?.sale_probability != null
        ? `${(prediction.sale_probability * 100).toFixed(0)}%`
        : "N/A";

  return (
    /* Restored app-shell class so the background system and font stack activate */
    <div className="app-shell">
      <video className="bg-video" autoPlay loop muted playsInline>
        <source src="/background.mp4" type="video/mp4" />
      </video>
      <div className="bg-overlay" />

      <div className="app-content">
        <h1 className="custom-text">PLAYSTAT</h1>
        {!selection && (
          <>
            <input
              type="text"
              value={steam_id}
              onChange={(e) => set_steam_id(e.target.value)}
              placeholder="76561197960434622"
            />
            <button onClick={lib_search} disabled={searching}>
              {searching ? "Loading..." : "Search"}
            </button>

            {searching && (
              <p style={{ color: "#c7d5e0" }}>
                Loading your library. If the server was asleep, the first load can take
                up to 30 seconds.
              </p>
            )}
            {search_error && <p style={{ color: "#e8a33d" }}>{search_error}</p>}

            {library?.games && (
              <ul className="game-list">
                {library.games.map((game) => (
                  <li
                    key={game.appid}
                    className="game-card"
                    onClick={() => set_selection(game)}
                  >
                    <div className="game-cover" style={coverStyle(game.appid)} />
                    <div className="game-info">
                      <h4>{game.name}</h4>
                      <div className="game-stats-row">
                        <p>
                          <Clock size={14} /> {(game.playtime_forever / 60).toFixed(1)} hours
                        </p>
                        <p className="recommend-percent">
                          {recommend_data[game.appid] === undefined ? (
                            "..."
                          ) : recommend_data[game.appid] === null ? (
                            "N/A"
                          ) : (
                            <>
                              <ThumbsUp size={14} /> {recommend_data[game.appid]}%
                            </>
                          )}
                        </p>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}

        {selection && (
          <div className="detail-view">
            <button className="back-button" onClick={() => set_selection(null)}>
              ← Back
            </button>

            <div className="detail-header">
              <div className="detail-cover" style={coverStyle(selection.appid)} />
              <div className="detail-header-text">
                <h2>{selection.name}</h2>
                <RatingWidget
                  appId={selection.appid}
                  steamId={steam_id}
                  initialStatus={user_ratings[selection.appid]?.status}
                  initialScore={user_ratings[selection.appid]?.score}
                />
                <p className="detail-hours">
                  {(selection.playtime_forever / 60).toFixed(1)} hours played
                </p>
              </div>
            </div>

            <div className="stat-grid">
              <div className="stat-card">
                <p className="stat-label">Next sale estimate</p>
                <p className="stat-value">{sale_text}</p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Sale probability</p>
                <p className="stat-value">{prediction_text}</p>
              </div>
            </div>

            <div className="detail-section">
              <h3>Discount history</h3>
              {history === undefined ? (
                <p>Loading...</p>
              ) : history?.length ? (
                <LineChart width={600} height={260} data={[...history].reverse()}>
                  <XAxis dataKey="timestamp" tick={false} stroke="#2a2f3a" />
                  <YAxis
                    dataKey="cut"
                    tick={{ fill: "#8a8f98", fontSize: 12 }}
                    stroke="#2a2f3a"
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#181b22",
                      border: "1px solid #262a33",
                      borderRadius: 8,
                    }}
                    labelStyle={{ color: "#8a8f98" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="cut"
                    stroke="#e8a33d"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              ) : (
                <p>No discount history available for this game.</p>
              )}
            </div>

            <div className="detail-section">
              <h3>What experienced players think (30+ hours)</h3>
              {reviews === undefined ? (
                <p>Loading...</p>
              ) : reviews?.reviews?.length ? (
                <div className="review-list">
                  {reviews.reviews.map((review, index) => (
                    <div className="review-card" key={index}>
                      <p>{review.review}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p>No reviews from 30+ hour players are available for this game.</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
