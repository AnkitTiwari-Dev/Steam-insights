import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";
import { Clock, ThumbsUp } from "lucide-react";
import "./App.css";
import RatingWidget from "./RatingWidget";
const API_BASE = "https://playstats.onrender.com";

function App() {
  const [user_ratings, set_user_ratings] = useState({});
  const [steam_id, set_steam_id] = useState("");
  const [library, set_library] = useState(null);
  const [selection, set_selection] = useState(null);
  const [sale_info, change_sale_info] = useState(null);
  const [prediction, set_prediction] = useState(null);
  const [reviews, set_reviews] = useState(null);
  const [history, set_history] = useState(null);
  const [recommend_data, set_recommend_data] = useState({});

  useEffect(() => {
    if (!selection) return;

    async function fetchSale() {
      const response = await fetch(`${API_BASE}/last_sale/${selection.appid}`);
      const data = await response.json();
      change_sale_info(data);
    }

    async function fetchRating(){
      const response = await fetch(`${API_BASE}/rating/${steam_id}`);
      const data = await response.json();
      set_user_ratings(data);
    }
    async function fetchPrediction() {
      const response = await fetch(`${API_BASE}/predict/${selection.appid}`);
      const data = await response.json();
      set_prediction(data);
    }

    async function fetchHistory() {
      const response = await fetch(`${API_BASE}/history/${selection.appid}`);
      if (!response.ok) {
        set_history(null);
        return;
      }
      const data = await response.json();
      set_history(data);
    }

    async function fetchReviews() {
      const response = await fetch(`${API_BASE}/reviews/${selection.appid}`);
      const data = await response.json();
      set_reviews(data);
    }

    fetchSale();
    fetchPrediction();
    fetchReviews();
    fetchHistory();
    fetchRating();
  }, [selection]);

  useEffect(() => {
    if (!library) return;

    async function fetchAllRecommendations() {
      const results = await Promise.all(
        library.games.map(async (game) => {
          const response = await fetch(`${API_BASE}/review_stats/${game.appid}`);
          const data = await response.json();
          return [game.appid, data.overall_percent];
        })
      );
      set_recommend_data(Object.fromEntries(results));
    }

    fetchAllRecommendations();
  }, [library]);

  async function lib_search() {
    const response = await fetch(`${API_BASE}/library/${steam_id}`);
    const data = await response.json();
    set_library(data);
  }

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
            <button onClick={lib_search}>Search</button>

            {library && (
              <ul className="game-list">
                {library.games.map((game) => (
                  <li
                    key={game.appid}
                    className="game-card"
                    onClick={() => set_selection(game)}
                  >
                    <div
                      className="game-cover"
                      style={{
                        backgroundImage: `url(https://cdn.akamai.steamstatic.com/steam/apps/${game.appid}/library_600x900.jpg)`
                    }}
                    />
                    <div className="game-info">
                      <h4>{game.name}</h4>
                      <div className="game-stats-row">
                        <p><Clock size={14} /> {(game.playtime_forever / 60).toFixed(1)} hours</p>
                        <p className="recommend-percent">
                          {recommend_data[game.appid] != null
                          ? <><ThumbsUp size={14} /> {recommend_data[game.appid]}%</>
                          : "..."}
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
      <div
        className="detail-cover"
        style={{
          backgroundImage: `url(https://cdn.akamai.steamstatic.com/steam/apps/${selection.appid}/library_600x900.jpg)`
        }}
      />
      <div className="detail-header-text">
        <h2>{selection.name}</h2>
          <RatingWidget
          appId={selection.appid}
          steamId={steam_id}
          initialStatus={user_ratings[selection.appid]?.status}
          initialScore={user_ratings[selection.appid]?.score}
          />
        <p className="detail-hours">{(selection.playtime_forever / 60).toFixed(1)} hours played</p>
      </div>
    </div>

    <div className="stat-grid">
      {sale_info && (
        <div className="stat-card">
          <p className="stat-label">Next sale estimate</p>
          <p className="stat-value">{new Date(sale_info.next_sale).toLocaleDateString()}</p>
        </div>
      )}
      {prediction && (
        <div className="stat-card">
          <p className="stat-label">Sale probability</p>
          <p className="stat-value">{(prediction.sale_probability * 100).toFixed(0)}%</p>
        </div>
      )}
    </div>

    {history && (
      <div className="detail-section">
        <h3>Discount history</h3>
        <LineChart width={600} height={260} data={[...history].reverse()}>
          <XAxis dataKey="timestamp" tick={false} stroke="#2a2f3a" />
          <YAxis dataKey="cut" tick={{ fill: "#8a8f98", fontSize: 12 }} stroke="#2a2f3a" />
          <Tooltip
            contentStyle={{ background: "#181b22", border: "1px solid #262a33", borderRadius: 8 }}
            labelStyle={{ color: "#8a8f98" }}
          />
          <Line type="monotone" dataKey="cut" stroke="#e8a33d" strokeWidth={2} dot={false} />
        </LineChart>
      </div>
    )}

    {reviews && (
      <div className="detail-section">
        <h3>What experienced players think (30+ hours)</h3>
        <div className="review-list">
          {reviews.reviews.map((review, index) => (
            <div className="review-card" key={index}>
              <p>{review.review}</p>
            </div>
          ))}
        </div>
      </div>
    )}
  </div>
)}
      </div>
    </div>
  );
}

export default App;
