import { useState, useEffect } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const STATUSES = ["skip it", "timepass", "go for it", "perfection"]
const STATUS_COLORS = {
  "skip it": "#f87171",
  "timepass": "#fbbf24",
  "go for it": "#34d399",
  "perfection": "#a78bfa",
};

function RatingWidget({ appId, steamId, initialStatus, initialScore }) {
  const [status, set_status] = useState(initialStatus || "");
  const [score, set_score] = useState(initialScore || "");
  const [saving, set_saving] = useState(false);

  useEffect(() => {
    set_status(initialStatus || "");
    set_score(initialScore || "");
  }, [appId, initialStatus, initialScore]);

  async function saveRating(nextStatus, nextScore) {
    set_saving(true);
    try {
      await fetch(`${API_BASE}/rating`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          app_id: appId,
          steam_id: steamId,
          status: nextStatus,
          score: nextScore === "" ? null : Number(nextScore),
        }),
      });
    } catch (e) {
      console.error("Failed to save rating", e);
    } finally {
      set_saving(false);
    }
  }

  function handleStatusClick(s) {
    set_status(s);
    saveRating(s, score);
  }

  function handleScoreChange(e) {
    set_score(e.target.value);
  }

  function handleScoreBlur() {
    if (status) saveRating(status, score);
  }

  return (
    <div className="rating-widget">
      <div className="rating-status-row">
        {STATUSES.map((s) => (
          <button
            key={s}
            className={`status-pill ${status === s ? "status-pill-active" : ""}`}
            style={{
                "--pill-color": STATUS_COLORS[s],
            }}
            onClick={() => handleStatusClick(s)}
          >
            <span className="status-dot" style={{ backgroundColor: STATUS_COLORS[s] }} />
            {s}
          </button>
        ))}
      </div>

      {status && (
        <div className="rating-score-row">
          <label htmlFor="score-input">Your score</label>
          <input
            id="score-input"
            type="number"
            min="1"
            max="10"
            value={score}
            onChange={handleScoreChange}
            onBlur={handleScoreBlur}
            placeholder="1-10"
          />
          {saving && <span className="rating-saving">saving…</span>}
        </div>
      )}
    </div>
  );
}

export default RatingWidget;