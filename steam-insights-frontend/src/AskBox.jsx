import { useState } from "react";

const MAX_QUESTION_CHARS = 300;

const TOOL_LABELS = {
  get_library: "your library",
  get_sale_prediction: "sale prediction",
  get_review_summary: "reviews",
};

const EXAMPLES = [
  "Which of my top games will probably go on sale soon?",
  "Are my most-played games still well reviewed?",
];

export default function AskBox({ apiBase, steamId }) {
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function ask(text) {
    const q = text.trim();
    if (!q || asking) return;

    setAsking(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${apiBase}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ steam_id: steamId, question: q }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        setError(
          typeof data?.detail === "string"
            ? data.detail
            : "The assistant could not answer that. Please try again."
        );
        return;
      }
      setResult(data);
    } catch (e) {
      console.error("Ask failed", e);
      setError("Could not reach the server. It may be waking up, so try again in a few seconds.");
    } finally {
      setAsking(false);
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    ask(question);
  }

  // Unique tool names, in the order the model first used them
  const toolsUsed = result?.tools_used
    ? [...new Set(result.tools_used.map((t) => TOOL_LABELS[t.name] ?? t.name))]
    : [];

  return (
    <section className="ask-box" aria-label="Ask about your library">
      <h3>Ask about your library</h3>

      <form className="ask-form" onSubmit={onSubmit}>
        <input
          type="text"
          value={question}
          maxLength={MAX_QUESTION_CHARS}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Which of my games is worth buying on sale?"
          aria-label="Your question"
          disabled={asking}
        />
        <button type="submit" disabled={asking || !question.trim()}>
          {asking ? "Thinking..." : "Ask"}
        </button>
      </form>

      {!result && !asking && !error && (
        <div className="ask-examples">
          {EXAMPLES.map((example) => (
            <button
              type="button"
              key={example}
              className="ask-example"
              onClick={() => {
                setQuestion(example);
                ask(example);
              }}
            >
              {example}
            </button>
          ))}
        </div>
      )}

      {asking && (
        <p className="ask-status" role="status">
          Checking your games. This can take up to 20 seconds.
        </p>
      )}

      {error && (
        <p className="ask-error" role="alert">
          {error}
        </p>
      )}

      {result && (
        <div className="ask-answer" role="status">
          <p>{result.answer}</p>
          {toolsUsed.length > 0 && (
            <p className="ask-sources">Looked at: {toolsUsed.join(", ")}</p>
          )}
        </div>
      )}
    </section>
  );
}
