import React, { useState, useEffect } from "react";
import axios from "axios";
import { Search, Mic, Volume2, ThumbsUp, ThumbsDown, Clock, FileText } from "lucide-react";
import "./App.css";

function App() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [fullSummaries, setFullSummaries] = useState({});
  const [listening, setListening] = useState(false);
  const [feedback, setFeedback] = useState({});
  const [history, setHistory] = useState([]);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = () => {
    axios.get("http://localhost:5000/history")
      .then(res => setHistory(res.data.history || []))
      .catch(() => setHistory([]));
  };

  const startListening = () => {
    if (!("webkitSpeechRecognition" in window)) {
      alert("Speech recognition is unsupported in this browser.");
      return;
    }
    const recognition = new window.webkitSpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => setListening(true);
    recognition.onend = () => setListening(false);

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setQuery(transcript);
    };

    recognition.onerror = (event) => {
      setListening(false);
      alert("Speech recognition error: " + event.error);
    };

    recognition.start();
  };

  const speakText = (text) => {
    if ("speechSynthesis" in window) {
      const utter = new SpeechSynthesisUtterance(text);
      window.speechSynthesis.speak(utter);
    } else {
      alert("Text-to-speech not supported in this browser.");
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    setError("");
    setResults([]);
    setLoading(true);
    setFullSummaries({});
    try {
      const response = await axios.get(
        `http://localhost:5000/search?q=${encodeURIComponent(query)}&limit=20`
      );
      setResults(response.data.results || []);
      fetchHistory();
      if (!response.data.results || response.data.results.length === 0) {
        setError("No results found for this query.");
      }
    } catch (err) {
      setError("Failed to fetch search results.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleFullSummary = async (link) => {
    setFullSummaries(prev => ({ ...prev, [link]: "Loading..." }));
    try {
      const response = await axios.get(
        `http://localhost:5000/summary?url=${encodeURIComponent(link)}`
      );
      setFullSummaries(prev => ({ ...prev, [link]: response.data.summary }));
    } catch {
      setFullSummaries(prev => ({ ...prev, [link]: "Could not fetch summary." }));
    }
  };

  const submitFeedback = async (url, category, summaryFeedback) => {
    try {
      await axios.post("http://localhost:5000/feedback", {
        url,
        category,
        summary_feedback: summaryFeedback,
      });
      setFeedback(prev => ({ ...prev, [url]: { category, summaryFeedback } }));
      alert("Feedback submitted! Thanks.");
    } catch {
      alert("Failed to send feedback.");
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-title">
            <Clock className="icon-clock" />
            <h3>Recent Searches</h3>
          </div>
        </div>
        <div className="sidebar-content">
          {history.length > 0 ? (
            <div className="history-list">
              {history.slice().reverse().map((q, idx) => (
                <button
                  key={idx}
                  onClick={() => { setQuery(q); handleSearch({ preventDefault: () => {} }); }}
                  className="history-item"
                  title={q}
                >
                  {q}
                </button>
              ))}
            </div>
          ) : (
            <p className="no-history">No recent searches yet</p>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <div className="content-wrapper">
          {/* Header */}
          <div className="header">
            <h1 className="title">Search Engine</h1>
            <p className="subtitle">Powered by AI-enhanced search technology</p>
          </div>

          {/* Search Form */}
          <form onSubmit={handleSearch} className="search-form">
            <div className="search-box">
              <div className="search-input-wrapper">
                <Search className="icon-search" />
                <input
                  type="text"
                  value={query}
                  placeholder="Enter your search query..."
                  onChange={(e) => setQuery(e.target.value)}
                  className="search-input"
                />
                <button
                  type="button"
                  onClick={startListening}
                  disabled={listening}
                  className={`btn-mic ${listening ? 'listening' : ''}`}
                  title="Voice search"
                >
                  <Mic className="icon" />
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="btn-search"
                >
                  {loading ? "Searching..." : "Search"}
                </button>
              </div>
            </div>
            {listening && (
              <p className="listening-text">🎤 Listening...</p>
            )}
          </form>

          {/* Error Message */}
          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          {/* Loading State */}
          {loading && (
            <div className="loading-container">
              <div className="spinner"></div>
            </div>
          )}

          {/* Results */}
          {results.length > 0 && (
            <div className="results-container">
              {results.map((item, idx) => (
                <div key={idx} className="result-card">
                  {/* Result Header */}
                  <a
                    href={item.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="result-link"
                  >
                    <h3 className="result-title">{item.title}</h3>
                  </a>

                  {/* Info Bar - Category & Full Summary */}
                  <div className="info-bar">
                    <div className="category-section">
                      <span className="info-icon">🏷️</span>
                      <div>
                        <p className="info-label">Category</p>
                        <p className="category-name">{item.category || "Uncategorized"}</p>
                      </div>
                    </div>
                    <div className="divider"></div>
                    <div className="full-summary-section">
                      <span className="info-icon">📄</span>
                      <div className="full-summary-action">
                        <p className="info-label">Full Analysis</p>
                        <button
                          onClick={() => handleFullSummary(item.link)}
                          className="btn-expand"
                        >
                          {fullSummaries[item.link] ? "Hide Details" : "View Details"}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Snippet */}
                  <div className="snippet-wrapper">
                    <p className="snippet-text">
                      <span className="snippet-label">Original:</span> {item.snippet}
                    </p>
                  </div>

                  {/* AI Summary */}
                  <div className="ai-summary">
                    <div className="summary-content">
                      <div className="summary-text-wrapper">
                        <p className="summary-label">AI Summary</p>
                        <p className="summary-text">{item.summary}</p>
                      </div>
                      <button
                        onClick={() => speakText(item.summary)}
                        className="btn-speak"
                        title="Listen to summary"
                      >
                        <Volume2 className="icon" />
                      </button>
                    </div>
                  </div>

                  {/* Full Summary Display */}
                  {fullSummaries[item.link] && (
                    <div className="full-summary">
                      <div className="full-summary-content">
                        <div className="full-summary-text-wrapper">
                          <p className="full-summary-label">
                            <FileText className="icon-inline" />
                            Complete Page Analysis
                          </p>
                          <p className="full-summary-text">{fullSummaries[item.link]}</p>
                        </div>
                        {fullSummaries[item.link] !== "Loading..." && fullSummaries[item.link] !== "Could not fetch summary." && (
                          <button
                            onClick={() => speakText(fullSummaries[item.link])}
                            className="btn-speak"
                            title="Listen to full summary"
                          >
                            <Volume2 className="icon" />
                          </button>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Feedback Section */}
                  <div className="feedback-section">
                    <span className="feedback-label">Was this summary helpful?</span>
                    <div className="feedback-buttons">
                      <button
                        disabled={feedback[item.link]?.summaryFeedback === "upvote"}
                        onClick={() => submitFeedback(item.link, item.category, "upvote")}
                        className={`btn-feedback ${feedback[item.link]?.summaryFeedback === "upvote" ? 'upvoted' : ''}`}
                      >
                        <ThumbsUp className="icon" />
                      </button>
                      <button
                        disabled={feedback[item.link]?.summaryFeedback === "downvote"}
                        onClick={() => submitFeedback(item.link, item.category, "downvote")}
                        className={`btn-feedback ${feedback[item.link]?.summaryFeedback === "downvote" ? 'downvoted' : ''}`}
                      >
                        <ThumbsDown className="icon" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;