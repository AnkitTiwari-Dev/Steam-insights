import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";
import { Clock, ThumbsUp } from "lucide-react";
import "./App.css";
const API_BASE = "https://playstats.onrender.com";

function App() {
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
      const response = await fetch(`${API_BASE}}/last_sale/${selection.appid}`);
      const data = await response.json();
      change_sale_info(data);
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
          <div>
            <button onClick={() => set_selection(null)}>Back</button>
            <h2>{selection.name}</h2>

            <div className="stat-grid">
              {sale_info && (
                <div className="stat-card">
                  <p>Next sale estimate</p>
                  <p>{new Date(sale_info.next_sale).toLocaleDateString()}</p>
                </div>
              )}
              {prediction && (
                <div className="stat-card">
                  <p>Sale probability</p>
                  <p>{(prediction.sale_probability * 100).toFixed(0)}%</p>
                </div>
              )}
            </div>

            {reviews && (
              <div>
                <h3>What experienced players think (30+ hours)</h3>
                <ul>
                  {reviews.reviews.map((review, index) => (
                    <li key={index}>{review.review}</li>
                  ))}
                </ul>
              </div>
            )}

            {history && (
              <div>
                <h3>Discount history</h3>
                <LineChart width={500} height={250} data={[...history].reverse()}>
                  <XAxis dataKey="timestamp" tick={false} />
                  <YAxis dataKey="cut" />
                  <Tooltip />
                  <Line type="monotone" dataKey="cut" stroke="#8884d8" />
                </LineChart>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
