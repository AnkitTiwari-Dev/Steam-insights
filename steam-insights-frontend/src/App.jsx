import { useState, useEffect } from "react";

function App() {
  const [steam_id, set_steam_id] = useState("");
  const [library, set_library] = useState(null);
  const [selection, set_selection] = useState(null);
  const [sale_info, change_sale_info] = useState(null);
  const [prediction, set_prediction] = useState(null);
  const [reviews, set_reviews] = useState(null);

  useEffect(() => {
    if (!selection) return;

    async function fetchSale() {
      const response = await fetch(`http://127.0.0.1:8000/last_sale/${selection.appid}`);
      const data = await response.json();
      change_sale_info(data);
    }

    async function fetchPrediction() {
    const response = await fetch(`http://127.0.0.1:8000/predict/${selection.appid}`);
    const data = await response.json();
    set_prediction(data);
  }

  async function fetchReviews() {
    const response = await fetch(`http://127.0.0.1:8000/reviews/${selection.appid}`);
    const data = await response.json();
    set_reviews(data);
  }

    fetchSale();
    fetchPrediction();
    fetchReviews();
  }, [selection]);

  async function lib_search() {
    const response = await fetch(`http://127.0.0.1:8000/library/${steam_id}`);
    const data = await response.json();
    set_library(data);
  }

  return (
    <div>
      <h1>Steam Insights</h1>

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
            <ul>
              {library.games.map((game) => (
                <li key={game.appid} onClick={() => set_selection(game)}>
                  {game.name} - {(game.playtime_forever / 60).toFixed(1)} hours
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
          {sale_info && <p>Next sale estimate: {sale_info.next_sale}</p>}
          {prediction && <p>Next predicted sale within 30 days: {(prediction.sale_probability * 100).toFixed(0)}%</p>}
          {reviews && (
            <div>
              <h3>What experienced players think(30+ hours)</h3>
              <ul>
                {reviews.reviews.map((review) =>(
                  <li key = {review.recommendationId}>{review.review}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;