"""Weekly market assessment runner for Is Kash Still Kashin?

Reads the last 7 daily snapshots from KV, pre-computes market deltas in Python,
then calls Gemini only for causal attribution and the sassy weekly wrap.
Saves the result to kash_weekly_assessment in KV.

Intended to run every Sunday via GitHub Actions (after the daily agent fires).
"""
import os
import json
import time
import logging
import requests
from datetime import datetime, timezone

from google import genai
from google.genai import types

def _load_dotenv():
    path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
KV_REST_URL    = os.environ.get("KV_REST_API_URL", "").rstrip("/")
KV_REST_TOKEN  = os.environ.get("KV_REST_API_TOKEN", "")

GEMINI_MODEL          = "gemini-flash-lite-latest"
DAILY_SNAPSHOTS_KEY   = "kash_daily_snapshots"
WEEKLY_ASSESSMENT_KEY = "kash_weekly_assessment"

WEEKLY_SYSTEM_PROMPT = """
You are the cynical, highly analytical, and aggressively sassy AI backend for "Is Kash Still Kashin?".

Your job this time is a WEEKLY MARKET ASSESSMENT — not a daily news verdict.

The factual numbers are pre-calculated for you. Do NOT recalculate or second-guess them.
Your only job is:
1. Attribute what drove the market movement this week (news events vs. passive time decay).
2. Write the sassy weekly wrap-up in the same voice as the daily summaries.

Return ONLY valid JSON:
{
  "driver": "news" | "time_decay" | "mixed" | "unclear",
  "driver_summary": "<1-2 sentences: factual attribution. Which specific events moved the needle? Or why does this look like pure time decay with no news catalyst? Be precise.>",
  "weekly_take": "<2-3 sentence sassy weekly wrap. Same cynical voice as the daily summaries — reference specific events, mock the situation, make it entertaining. Max 80 words.>"
}
"""

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

class _UTCFormatter(logging.Formatter):
    converter = time.gmtime

def setup_logging(level: int = logging.DEBUG) -> None:
    fmt = _UTCFormatter(
        fmt="%(asctime)s  %(levelname)-8s %(name)-10s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)

log_weekly = logging.getLogger("weekly")
log_kv     = logging.getLogger("kv")
log_gemini = logging.getLogger("gemini")

# ---------------------------------------------------------------------------
# KV HELPERS
# ---------------------------------------------------------------------------

def _kv_headers() -> dict:
    return {
        "Authorization": f"Bearer {KV_REST_TOKEN}",
        "Content-Type":  "application/json",
    }

def load_daily_snapshots(n: int = 7) -> list[dict]:
    """Load the last n daily snapshots. Returns in chronological order (oldest first)."""
    if not KV_REST_URL or not KV_REST_TOKEN:
        log_kv.warning("KV credentials missing — cannot load snapshots")
        return []
    try:
        resp = requests.get(
            f"{KV_REST_URL}/lrange/{DAILY_SNAPSHOTS_KEY}/0/{n - 1}",
            headers=_kv_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        raw_list = resp.json().get("result") or []
        snapshots = []
        for item in raw_list:
            try:
                snap = json.loads(item) if isinstance(item, str) else item
                snapshots.append(snap)
            except Exception:
                continue
        # LPUSH order: index 0 = most recent; reverse for chronological order
        snapshots.reverse()
        log_kv.info(f"Loaded {len(snapshots)} daily snapshots")
        return snapshots
    except Exception as e:
        log_kv.error(f"Failed to load daily snapshots  error={e}")
        return []

def save_weekly_assessment(assessment: dict):
    if not KV_REST_URL or not KV_REST_TOKEN:
        log_kv.warning("KV credentials missing — skipping weekly assessment save")
        return
    try:
        resp = requests.post(
            f"{KV_REST_URL}/set/{WEEKLY_ASSESSMENT_KEY}",
            headers=_kv_headers(),
            json=assessment,
            timeout=10,
        )
        resp.raise_for_status()
        log_kv.info(f"Weekly assessment saved  key={WEEKLY_ASSESSMENT_KEY}")
    except Exception as e:
        log_kv.error(f"Weekly assessment save failed  error={e}")

# ---------------------------------------------------------------------------
# STATS COMPUTATION (pure Python — no LLM)
# ---------------------------------------------------------------------------

def _market_stats(snapshots: list[dict], prob_key: str) -> dict:
    """Compute open/close/delta/pct for one market across chronological snapshots."""
    data = [s for s in snapshots if s.get(prob_key) is not None]
    if not data:
        return {"open": None, "close": None, "delta": None, "pct_change": None}
    open_val  = data[0][prob_key]
    close_val = data[-1][prob_key]
    delta     = round(close_val - open_val, 4)
    pct_change = round((delta / open_val) * 100, 1) if open_val else None
    return {
        "open":       round(open_val, 4),
        "close":      round(close_val, 4),
        "delta":      delta,
        "pct_change": pct_change,
    }

def compute_market_stats(snapshots: list[dict]) -> dict:
    """snapshots in chronological order (oldest first)."""
    kalshi = _market_stats(snapshots, "kalshi_prob")
    poly   = _market_stats(snapshots, "polymarket_prob")

    delta_ref = kalshi["delta"] if kalshi["delta"] is not None else poly["delta"]
    if delta_ref is None:
        direction = "flat"
    elif delta_ref > 0.005:
        direction = "up"
    elif delta_ref < -0.005:
        direction = "down"
    else:
        direction = "flat"

    markets_agree = False
    if kalshi["delta"] is not None and poly["delta"] is not None:
        markets_agree = (kalshi["delta"] >= 0) == (poly["delta"] >= 0)

    return {
        "kalshi":        kalshi,
        "polymarket":    poly,
        "direction":     direction,
        "markets_agree": markets_agree,
    }

def build_price_summary(stats: dict) -> str:
    k = stats["kalshi"]
    p = stats["polymarket"]
    direction = stats["direction"].upper()
    parts = []
    if k["open"] is not None:
        parts.append(
            f"Kalshi: {k['open']*100:.1f}% → {k['close']*100:.1f}%"
            f" (Δ {k['delta']*100:+.1f}pts, {k['pct_change']:+.1f}%)"
        )
    if p["open"] is not None:
        parts.append(
            f"Polymarket: {p['open']*100:.1f}% → {p['close']*100:.1f}%"
            f" (Δ {p['delta']*100:+.1f}pts, {p['pct_change']:+.1f}%)"
        )
    agree_str = "agree" if stats["markets_agree"] else "disagree"
    summary = f"Both markets moved {direction} this week. " + "  ".join(parts)
    if len(parts) == 2:
        summary += f"  Markets {agree_str} on direction."
    return summary

# ---------------------------------------------------------------------------
# PROMPT BUILDER
# ---------------------------------------------------------------------------

def build_weekly_prompt(snapshots: list[dict], stats: dict, week_of: str) -> str:
    k = stats["kalshi"]
    p = stats["polymarket"]
    lines = ["MARKET STATS (pre-calculated, treat as ground truth):"]
    if k["open"] is not None:
        lines.append(
            f"  Kalshi:     {k['open']*100:.1f}% → {k['close']*100:.1f}%"
            f"  (Δ {k['delta']*100:+.1f}pts, {k['pct_change']:+.1f}%)"
        )
    if p["open"] is not None:
        lines.append(
            f"  Polymarket: {p['open']*100:.1f}% → {p['close']*100:.1f}%"
            f"  (Δ {p['delta']*100:+.1f}pts, {p['pct_change']:+.1f}%)"
        )
    agree_str = "YES" if stats["markets_agree"] else "NO"
    lines.append(f"  Direction: {stats['direction'].upper()}  |  Markets agree: {agree_str}")
    lines.append("")
    lines.append("DAILY EVENTS (oldest → newest):")
    for snap in snapshots:
        date    = snap.get("date", "?")
        verdict = snap.get("verdict", "?")
        conf    = snap.get("confidence") or 0
        events  = snap.get("key_events") or []
        reason  = snap.get("reason", "")
        events_str = ", ".join(f'"{e}"' for e in events) if events else "(no events logged)"
        lines.append(f"  {date} [{verdict} {conf:.0%}]: {events_str}")
        if reason:
            lines.append(f"    reason: {reason}")
    lines.append("")
    lines.append(f"Week of: {week_of}")
    lines.append("Return your JSON assessment.")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# LLM CALL
# ---------------------------------------------------------------------------

def call_gemini_weekly(prompt: str) -> tuple[dict, dict]:
    if not GEMINI_API_KEY:
        log_gemini.warning("GEMINI_API_KEY not set — skipping weekly LLM call")
        return {}, {}

    client = genai.Client(api_key=GEMINI_API_KEY)
    log_gemini.info(f"Calling Gemini for weekly assessment  model={GEMINI_MODEL}")
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=WEEKLY_SYSTEM_PROMPT,
                temperature=0.3,
                max_output_tokens=300,
                response_mime_type="application/json",
            ),
        )
        result = json.loads(response.text)
        token_usage = {}
        try:
            token_usage = {
                "prompt_tokens":     response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
            }
        except Exception:
            pass
        log_gemini.info(
            f"Weekly assessment OK  driver={result.get('driver')}"
            f"  tokens_in={token_usage.get('prompt_tokens', '?')}"
            f"  tokens_out={token_usage.get('completion_tokens', '?')}"
        )
        return result, token_usage
    except json.JSONDecodeError as e:
        log_gemini.error(f"JSON parse failed  error={e}")
        return {}, {}
    except Exception as e:
        log_gemini.error(f"Weekly Gemini call failed  error={e}")
        return {}, {}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    setup_logging()
    now     = datetime.now(timezone.utc)
    now_str = now.isoformat()

    log_weekly.info("=" * 56)
    log_weekly.info(f"Weekly assessment starting  date={now_str[:10]}")
    log_weekly.info("=" * 56)

    snapshots = load_daily_snapshots(7)
    if len(snapshots) < 2:
        log_weekly.warning(
            f"Not enough snapshots for weekly assessment  count={len(snapshots)} (need ≥2)"
        )
        return

    week_of = snapshots[0]["date"]

    stats         = compute_market_stats(snapshots)
    price_summary = build_price_summary(stats)
    log_weekly.info(
        f"Market stats computed  direction={stats['direction']}"
        f"  kalshi_delta={stats['kalshi']['delta']}"
        f"  poly_delta={stats['polymarket']['delta']}"
    )

    prompt = build_weekly_prompt(snapshots, stats, week_of)
    log_weekly.debug(f"Weekly prompt:\n{prompt}")

    llm_result, token_usage = call_gemini_weekly(prompt)
    if not llm_result:
        log_weekly.error("Weekly LLM call failed — aborting")
        return

    k = stats["kalshi"]
    p = stats["polymarket"]
    assessment = {
        "week_of":               week_of,
        "generated_at":          now_str,
        "snapshots_used":        len(snapshots),
        "kalshi_open":           k["open"],
        "kalshi_close":          k["close"],
        "kalshi_delta":          k["delta"],
        "kalshi_pct_change":     k["pct_change"],
        "polymarket_open":       p["open"],
        "polymarket_close":      p["close"],
        "polymarket_delta":      p["delta"],
        "polymarket_pct_change": p["pct_change"],
        "direction":             stats["direction"],
        "markets_agree":         stats["markets_agree"],
        "price_summary":         price_summary,
        "driver":                llm_result.get("driver"),
        "driver_summary":        llm_result.get("driver_summary"),
        "weekly_take":           llm_result.get("weekly_take"),
        "token_usage":           token_usage,
    }

    log_weekly.info(f"\n{json.dumps(assessment, indent=2)}")
    save_weekly_assessment(assessment)

    log_weekly.info("=" * 56)
    log_weekly.info(
        f"Weekly assessment complete  week_of={week_of}"
        f"  driver={assessment['driver']}"
    )
    log_weekly.info("=" * 56)


if __name__ == "__main__":
    main()
