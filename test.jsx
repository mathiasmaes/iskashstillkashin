import { useState, useEffect } from "react";
 
function StarField() {
  return (
    <div style={{
      position: "absolute",
      top: 0, left: 0, right: 0,
      height: "200px",
      overflow: "hidden",
      opacity: 0.15,
      pointerEvents: "none",
    }}>
      {Array.from({ length: 40 }).map((_, i) => (
        <span key={i} style={{
          position: "absolute",
          left: `${(i * 37) % 100}%`,
          top: `${(i * 23) % 100}%`,
          color: "#fff",
          fontSize: `${8 + (i % 3) * 4}px`,
          animation: `twinkle ${2 + (i % 3)}s ease-in-out infinite`,
          animationDelay: `${i * 0.1}s`,
        }}>★</span>
      ))}
    </div>
  );
}
 
function StripesBar() {
  return (
    <div style={{
      height: "12px",
      display: "flex",
      width: "100%",
    }}>
      {Array.from({ length: 13 }).map((_, i) => (
        <div key={i} style={{
          flex: 1,
          background: i % 2 === 0 ? "#B22234" : "#fff",
        }} />
      ))}
    </div>
  );
}
 
function EagleSeal({ status }) {
  const color = status === null ? "#888" : status ? "#0a5c2e" : "#B22234";
  return (
    <div style={{
      width: 140,
      height: 140,
      borderRadius: "50%",
      border: `6px double ${color}`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      margin: "0 auto",
      background: "#fff",
      boxShadow: `0 0 0 4px #fff, 0 0 0 6px ${color}, 0 8px 24px rgba(0,0,0,0.3)`,
      position: "relative",
    }}>
      <div style={{
        fontSize: "72px",
        filter: status === null ? "grayscale(1)" : "none",
      }}>🦅</div>
      <div style={{
        position: "absolute",
        bottom: -8,
        left: "50%",
        transform: "translateX(-50%)",
        background: color,
        color: "#fff",
        fontSize: "9px",
        letterSpacing: "0.2em",
        padding: "3px 10px",
        fontFamily: "'Oswald', sans-serif",
        fontWeight: 700,
      }}>
        OFFICIAL
      </div>
    </div>
  );
}
 
function MarketOddsCard({ market }) {
  const pct = market.yesPercent;
  const color = pct >= 70 ? "#0a5c2e" : pct >= 40 ? "#d4a017" : "#B22234";
  return (
    <div style={{
      background: "#fff",
      border: "2px solid #0a1747",
      padding: "20px",
      marginBottom: "12px",
      position: "relative",
    }}>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        marginBottom: "12px",
        gap: "16px",
      }}>
        <div>
          <div style={{
            fontFamily: "'Oswald', sans-serif",
            fontSize: "10px",
            letterSpacing: "0.2em",
            color: "#B22234",
            fontWeight: 700,
            marginBottom: "4px",
          }}>
            {market.platform}
          </div>
          <div style={{
            fontFamily: "Georgia, serif",
            fontSize: "13px",
            color: "#0a1747",
            lineHeight: "1.4",
            fontWeight: 600,
          }}>
            {market.question}
          </div>
        </div>
        <div style={{
          fontFamily: "'Oswald', sans-serif",
          fontSize: "36px",
          fontWeight: 900,
          color: color,
          lineHeight: 1,
          whiteSpace: "nowrap",
        }}>
          {pct}%
        </div>
      </div>
      {/* Odds bar */}
      <div style={{
        height: "8px",
        background: "#eee",
        position: "relative",
        overflow: "hidden",
      }}>
        <div style={{
          position: "absolute",
          left: 0, top: 0, bottom: 0,
          width: `${pct}%`,
          background: `linear-gradient(90deg, ${color}, ${color}dd)`,
          transition: "width 1.2s cubic-bezier(0.4, 0, 0.2, 1)",
        }} />
      </div>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        marginTop: "6px",
        fontFamily: "'Oswald', sans-serif",
        fontSize: "9px",
        letterSpacing: "0.15em",
        color: "#666",
      }}>
        <span>YES {pct}¢</span>
        <span>NO {100 - pct}¢</span>
      </div>
    </div>
  );
}
 
function NewsCard({ article, index }) {
  return (
    <div style={{
      background: "#fff",
      border: "2px solid #0a1747",
      borderLeft: "6px solid #B22234",
      padding: "16px 20px",
      marginBottom: "12px",
      animation: `slideIn 0.5s ease forwards`,
      animationDelay: `${index * 0.1}s`,
      opacity: 0,
    }}>
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        marginBottom: "8px",
      }}>
        <span style={{
          background: "#0a1747",
          color: "#fff",
          fontFamily: "'Oswald', sans-serif",
          fontSize: "9px",
          letterSpacing: "0.2em",
          padding: "3px 8px",
          fontWeight: 700,
        }}>
          {article.source}
        </span>
        {article.date && (
          <span style={{
            fontFamily: "'Oswald', sans-serif",
            fontSize: "10px",
            color: "#888",
            letterSpacing: "0.1em",
          }}>
            {article.date}
          </span>
        )}
      </div>
      <div style={{
        fontFamily: "Georgia, serif",
        fontSize: "14px",
        color: "#222",
        lineHeight: "1.55",
        marginBottom: "8px",
      }}>
        {article.summary}
      </div>
      {article.url && (
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{
            fontFamily: "'Oswald', sans-serif",
            fontSize: "10px",
            letterSpacing: "0.2em",
            color: "#B22234",
            textDecoration: "none",
            fontWeight: 700,
            borderBottom: "1px solid #B22234",
            paddingBottom: "1px",
          }}
        >
          READ FULL ARTICLE →
        </a>
      )}
    </div>
  );
}
 
export default function App() {
  const [status, setStatus] = useState(null);
  const [headline, setHeadline] = useState("");
  const [news, setNews] = useState([]);
  const [markets, setMarkets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [checked, setChecked] = useState(false);
  const [lastChecked, setLastChecked] = useState(null);
  const [error, setError] = useState(null);
  const [loadingStep, setLoadingStep] = useState("");
 
  async function checkStatus() {
    setLoading(true);
    setChecked(false);
    setError(null);
    setNews([]);
    setMarkets([]);
    setStatus(null);
 
    const steps = [
      "DEPLOYING AGENT...",
      "SCANNING NYT...",
      "CHECKING POLYMARKET...",
      "CHECKING KALSHI...",
      "COMPILING REPORT...",
    ];
    let stepIdx = 0;
    setLoadingStep(steps[0]);
    const stepInterval = setInterval(() => {
      stepIdx = (stepIdx + 1) % steps.length;
      setLoadingStep(steps[stepIdx]);
    }, 1200);
 
    try {
      const today = new Date().toLocaleDateString("en-US", {
        month: "long", day: "numeric", year: "numeric"
      });
 
      const response = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 2000,
          tools: [{ type: "web_search_20250305", name: "web_search" }],
          system: `You are an agentic news analyst. Today is ${today}.
 
Your job has two parts:
1. Determine if Kash Patel is currently the FBI Director by searching the New York Times and other reputable news sources.
2. Find prediction market odds on Polymarket and/or Kalshi for markets about whether Kash Patel will remain/be FBI Director by a given date.
 
Use web search to gather this information. Then respond with ONLY a valid JSON object (no markdown fences, no prose before or after) in this exact shape:
{
  "isDirector": true | false,
  "headline": "One sharp sentence stating his current status as of today.",
  "news": [
    {
      "source": "NYT",
      "date": "Apr 20, 2026",
      "summary": "2-3 sentence summary.",
      "url": "https://..."
    }
  ],
  "markets": [
    {
      "platform": "POLYMARKET",
      "question": "Will Kash Patel be FBI Director on [date]?",
      "yesPercent": 87,
      "url": "https://..."
    }
  ]
}
 
Include 2-3 news items (NYT preferred, but other reputable sources OK if NYT has nothing fresh). Include 1-3 prediction markets if you can find them. If no markets exist, return an empty markets array. yesPercent must be an integer 0-100.`,
          messages: [
            {
              role: "user",
              content: `Check if Kash Patel is still the FBI Director as of today. Also find any Polymarket or Kalshi prediction markets about his tenure as FBI Director and report their current odds.`
            }
          ]
        })
      });
 
      const data = await response.json();
      const textBlocks = data.content?.filter(b => b.type === "text") || [];
      const fullText = textBlocks.map(b => b.text).join("\n");
 
      // Strip markdown fences if present
      let clean = fullText.replace(/```json|```/g, "").trim();
      // Try to extract JSON if wrapped in prose
      const jsonMatch = clean.match(/\{[\s\S]*\}/);
      if (jsonMatch) clean = jsonMatch[0];
 
      const parsed = JSON.parse(clean);
 
      setStatus(parsed.isDirector);
      setHeadline(parsed.headline || "");
      setNews(parsed.news || []);
      setMarkets(parsed.markets || []);
      setLastChecked(new Date());
      setChecked(true);
    } catch (err) {
      setError("Intel retrieval failed. Try again.");
      console.error(err);
    } finally {
      clearInterval(stepInterval);
      setLoading(false);
      setLoadingStep("");
    }
  }
 
  useEffect(() => { checkStatus(); }, []);
 
  const verdictColor = status === null ? "#888" : status ? "#0a5c2e" : "#B22234";
  const verdictText = status === null ? "—" : status ? "YES" : "NO";
 
  return (
    <div style={{
      minHeight: "100vh",
      background: "#f4f1e8",
      fontFamily: "Georgia, serif",
      color: "#0a1747",
      position: "relative",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&family=Special+Elite&display=swap');
 
        @keyframes twinkle {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }
        @keyframes slideIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes stampIn {
          0% { transform: scale(3) rotate(-20deg); opacity: 0; }
          60% { transform: scale(0.9) rotate(-12deg); opacity: 1; }
          100% { transform: scale(1) rotate(-8deg); opacity: 1; }
        }
        @keyframes flicker {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
 
        .btn-primary {
          background: #B22234;
          color: #fff;
          border: 3px solid #0a1747;
          padding: 14px 32px;
          font-family: 'Oswald', sans-serif;
          font-size: 13px;
          font-weight: 700;
          letter-spacing: 0.25em;
          cursor: pointer;
          text-transform: uppercase;
          box-shadow: 4px 4px 0 #0a1747;
          transition: all 0.15s;
        }
        .btn-primary:hover:not(:disabled) {
          transform: translate(-2px, -2px);
          box-shadow: 6px 6px 0 #0a1747;
        }
        .btn-primary:disabled {
          opacity: 0.6;
          cursor: wait;
        }
      `}</style>
 
      {/* Top stripes */}
      <StripesBar />
 
      {/* Blue header with stars */}
      <div style={{
        background: "#0a1747",
        padding: "30px 20px 40px",
        position: "relative",
        overflow: "hidden",
        textAlign: "center",
      }}>
        <StarField />
        <div style={{
          fontFamily: "'Oswald', sans-serif",
          fontSize: "10px",
          letterSpacing: "0.35em",
          color: "#f4f1e8",
          opacity: 0.7,
          marginBottom: "8px",
          position: "relative",
        }}>
          ★ ★ ★ CITIZEN INTELLIGENCE BUREAU ★ ★ ★
        </div>
        <h1 style={{
          fontFamily: "'Oswald', sans-serif",
          fontSize: "clamp(28px, 6vw, 56px)",
          fontWeight: 700,
          letterSpacing: "-0.01em",
          color: "#fff",
          margin: "0 0 4px 0",
          position: "relative",
          lineHeight: 1,
        }}>
          IS KASH PATEL
        </h1>
        <h1 style={{
          fontFamily: "'Oswald', sans-serif",
          fontSize: "clamp(28px, 6vw, 56px)",
          fontWeight: 700,
          letterSpacing: "-0.01em",
          color: "#B22234",
          margin: 0,
          position: "relative",
          lineHeight: 1,
          textShadow: "2px 2px 0 #fff",
        }}>
          STILL CASHING?
        </h1>
      </div>
 
      <StripesBar />
 
      {/* Main */}
      <div style={{
        maxWidth: 720,
        margin: "0 auto",
        padding: "50px 24px",
      }}>
 
        {/* VERDICT */}
        <div style={{
          background: "#fff",
          border: "4px solid #0a1747",
          padding: "40px 20px",
          textAlign: "center",
          position: "relative",
          marginBottom: "30px",
          boxShadow: "8px 8px 0 #B22234",
        }}>
          <div style={{
            fontFamily: "'Oswald', sans-serif",
            fontSize: "11px",
            letterSpacing: "0.35em",
            color: "#666",
            marginBottom: "16px",
            fontWeight: 600,
          }}>
            TODAY'S VERDICT
          </div>
 
          {loading ? (
            <div>
              <div style={{
                fontFamily: "'Oswald', sans-serif",
                fontSize: "clamp(80px, 18vw, 140px)",
                fontWeight: 700,
                color: "#ddd",
                lineHeight: 1,
                marginBottom: "12px",
              }}>?</div>
              <div style={{
                fontFamily: "'Special Elite', monospace",
                fontSize: "12px",
                color: "#B22234",
                letterSpacing: "0.2em",
                animation: "flicker 1s ease-in-out infinite",
              }}>
                {loadingStep}
              </div>
            </div>
          ) : (
            <>
              <div style={{
                fontFamily: "'Oswald', sans-serif",
                fontSize: "clamp(100px, 22vw, 180px)",
                fontWeight: 700,
                color: verdictColor,
                lineHeight: 0.9,
                letterSpacing: "-0.03em",
                textShadow: checked ? `3px 3px 0 #0a1747` : "none",
                transform: checked ? "rotate(-2deg)" : "none",
                display: "inline-block",
                animation: checked ? "stampIn 0.6s ease-out" : "none",
              }}>
                {verdictText}
              </div>
              {checked && (
                <div style={{
                  marginTop: "20px",
                  fontFamily: "Georgia, serif",
                  fontSize: "15px",
                  color: "#333",
                  fontStyle: "italic",
                  lineHeight: 1.5,
                  maxWidth: "500px",
                  margin: "20px auto 0",
                }}>
                  "{headline}"
                </div>
              )}
            </>
          )}
        </div>
 
        {/* Eagle seal row */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "20px",
          marginBottom: "40px",
        }}>
          <EagleSeal status={status} />
        </div>
 
        {error && (
          <div style={{
            background: "#B22234",
            color: "#fff",
            padding: "16px 20px",
            fontFamily: "'Oswald', sans-serif",
            fontSize: "12px",
            letterSpacing: "0.15em",
            textAlign: "center",
            marginBottom: "30px",
          }}>
            ⚠ {error}
          </div>
        )}
 
        {/* Refresh */}
        <div style={{ textAlign: "center", marginBottom: "50px" }}>
          <button className="btn-primary" onClick={checkStatus} disabled={loading}>
            {loading ? "INVESTIGATING..." : "↻ REFRESH INTEL"}
          </button>
          {lastChecked && (
            <div style={{
              marginTop: "12px",
              fontFamily: "'Special Elite', monospace",
              fontSize: "11px",
              color: "#666",
              letterSpacing: "0.1em",
            }}>
              Last checked: {lastChecked.toLocaleString()}
            </div>
          )}
        </div>
 
        {/* Prediction markets */}
        {checked && markets.length > 0 && (
          <div style={{ marginBottom: "50px" }}>
            <div style={{
              borderTop: "3px double #0a1747",
              borderBottom: "3px double #0a1747",
              padding: "12px 0",
              marginBottom: "20px",
              textAlign: "center",
            }}>
              <h2 style={{
                fontFamily: "'Oswald', sans-serif",
                fontSize: "18px",
                fontWeight: 700,
                letterSpacing: "0.3em",
                margin: 0,
                color: "#0a1747",
              }}>
                📊 THE SMART MONEY SAYS
              </h2>
              <div style={{
                fontFamily: "'Special Elite', monospace",
                fontSize: "10px",
                color: "#666",
                marginTop: "4px",
                letterSpacing: "0.15em",
              }}>
                LIVE PREDICTION MARKET ODDS
              </div>
            </div>
            {markets.map((m, i) => <MarketOddsCard key={i} market={m} />)}
          </div>
        )}
 
        {/* News */}
        {checked && news.length > 0 && (
          <div>
            <div style={{
              borderTop: "3px double #0a1747",
              borderBottom: "3px double #0a1747",
              padding: "12px 0",
              marginBottom: "20px",
              textAlign: "center",
            }}>
              <h2 style={{
                fontFamily: "'Oswald', sans-serif",
                fontSize: "18px",
                fontWeight: 700,
                letterSpacing: "0.3em",
                margin: 0,
                color: "#0a1747",
              }}>
                📰 LATEST FROM THE WIRE
              </h2>
            </div>
            {news.map((a, i) => <NewsCard key={i} article={a} index={i} />)}
          </div>
        )}
      </div>
 
      <StripesBar />
      <div style={{
        background: "#0a1747",
        color: "#f4f1e8",
        padding: "30px 20px",
        textAlign: "center",
        fontFamily: "'Oswald', sans-serif",
        fontSize: "10px",
        letterSpacing: "0.3em",
      }}>
        ★ POWERED BY AGENTIC AI · NOT AFFILIATED WITH THE FBI OR ANY GOVERNMENT AGENCY ★
      </div>
    </div>
  );
}