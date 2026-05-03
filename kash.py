"""
Is Kash Till Cashing — Phase 1 Agent
Runs on GitHub Actions twice daily.
Fetches Google News RSS, reads articles via Jina Reader,
sends to Gemini 2.5 Flash-Lite, and uploads result to Vercel KV.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import json
import time
import feedparser
import requests
import google.generativeai as genai
from datetime import datetime, timezone



# ─── CONFIG ──────────────────────────────────────────────────────────────────

RSS_QUERY      = "Kash+Patel+FBI+Director"
RSS_URL        = f"https://news.google.com/rss/search?q={RSS_QUERY}&hl=en-US&gl=US&ceid=US:en"
MAX_ARTICLES   = 5
ARTICLE_CHARS  = 1500          # max chars per article sent to LLM
JINA_BASE      = "https://r.jina.ai/"
GEMINI_MODEL   = "gemini-2.0-flash-lite"
MAX_TOKENS     = 800
TEMPERATURE    = 0.1
SCHEMA_VERSION = "1.0"
KV_KEY         = "kash_status_latest"

# ─── CREDENTIALS (from environment / GitHub Secrets) ─────────────────────────

GEMINI_API_KEY  = os.environ.get("GEMINI_API_KEY", "")
KV_REST_URL     = os.environ.get("KV_REST_API_URL", "")
KV_REST_TOKEN   = os.environ.get("KV_REST_API_TOKEN", "")
JINA_API_KEY    = os.environ.get("JINA_API_KEY", "")   # optional
GITHUB_RUN_ID   = os.environ.get("GITHUB_RUN_ID", "local")

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are the intelligence core of "Is Kash Till Cashing", a satirical but
factually strict tracker monitoring whether Kash Patel is currently serving
as FBI Director of the United States.

══════════════════════════════════
 KASH PATEL LORE  (use for satire)
══════════════════════════════════
- Wrote a children's book series portraying Trump as "King Donald" and
  himself as "Kash the Distinguished Discoverer" — a wizard fighting the
  "Deep State dragon".
- Runs "Kash" branded merchandise.
- Known for absolute loyalty to Trump and anti-Deep State rhetoric.
- Rumours of heavy drinking and partying have followed him throughout his
  tenure at the FBI.
- Was previously removed as acting head of the ATF.

══════════════════════════════════
 HUMOR STYLE GUIDE
══════════════════════════════════
- Tone: sardonic, politically cynical, occasionally exhausted.
- Use metaphors that connect to his lore (wizard, Deep State dragon-slayer,
  his children's book, his branding, his rumored extracurriculars).
- Never invent facts. Humor must be grounded in the supplied articles.
- Example of BAD tone: "Kash is still there. People are mad. Very funny."
- Example of GOOD tone: "The Distinguished Discoverer survives another
  Tuesday at the Hoover Building, reportedly still casting spells at the
  Deep State while budget hawks sharpened their axes downstairs."

══════════════════════════════════
 YOUR TASK
══════════════════════════════════
Read the provided news articles carefully.

Step 1 — Factual analysis (private):
  Determine whether Kash Patel is currently still serving as FBI Director.
  Look for keywords: fired, resigned, removed, replaced, acting director,
  no longer, steps down, departure. If none are present from credible
  sourcing, the status is YES (still in post).

Step 2 — Announcement check:
  Determine whether any credible source has announced or confirmed a
  coming departure (even if he has not yet left).

Step 3 — Output strict JSON only. No markdown. No preamble.

══════════════════════════════════
 OUTPUT JSON SCHEMA (strict)
══════════════════════════════════
{
  "status_now": "YES" or "NO",
  "announcement_made": "YES" or "NO",
  "agent_chain_of_thought": "<dry 1-3 sentence factual reasoning>",
  "sassy_summary": "<50 to 100 words, satirical, grounded in the news>"
}
"""

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def fetch_rss_entries():
    """Fetch and return up to MAX_ARTICLES entries from Google News RSS."""
    print(f"[rss] Fetching: {RSS_URL}")
    try:
        feed = feedparser.parse(RSS_URL)
        entries = feed.entries[:MAX_ARTICLES]
        print(f"[rss] Retrieved {len(entries)} entries.")
        return entries, "success"
    except Exception as e:
        print(f"[rss] FAILED: {e}")
        return [], "failed"


def read_article_via_jina(url: str) -> str:
    """Read an article URL through Jina Reader and return truncated text."""
    jina_url = f"{JINA_BASE}{url}"
    headers = {"Accept": "text/plain"}
    if JINA_API_KEY:
        headers["Authorization"] = f"Bearer {JINA_API_KEY}"
    try:
        resp = requests.get(jina_url, headers=headers, timeout=15)
        resp.raise_for_status()
        text = resp.text[:ARTICLE_CHARS]
        print(f"[jina] OK — {len(text)} chars from {url[:60]}...")
        return text
    except Exception as e:
        print(f"[jina] FAILED for {url[:60]}: {e}")
        return ""


def build_article_context(entries: list) -> tuple[str, list]:
    """Build a combined context string and sources list from RSS entries."""
    context_parts = []
    sources = []

    for i, entry in enumerate(entries, 1):
        title       = getattr(entry, "title", "No title")
        url         = getattr(entry, "link",  "")
        published   = getattr(entry, "published", "")

        print(f"[article {i}/{len(entries)}] {title}")
        text = read_article_via_jina(url)

        if text:
            context_parts.append(
                f"--- ARTICLE {i} ---\n"
                f"Title: {title}\n"
                f"Published: {published}\n"
                f"Text:\n{text}\n"
            )

        sources.append({
            "title":        title,
            "url":          url,
            "published_at": published,
        })

    return "\n".join(context_parts), sources


def call_gemini(context: str) -> tuple[dict, str, dict]:
    """Call Gemini and return (parsed_verdict, status, token_usage)."""
    genai.configure(api_key=GEMINI_API_KEY)

    generation_config = genai.GenerationConfig(
        temperature=TEMPERATURE,
        max_output_tokens=MAX_TOKENS,
        response_mime_type="application/json",
    )

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config=generation_config,
    )

    user_message = (
        "Here are the latest news articles about Kash Patel. "
        "Analyze them and return your JSON verdict.\n\n"
        + context
    )

    try:
        response = model.generate_content(user_message)
        raw_text = response.text
        print(f"[gemini] Raw response: {raw_text[:300]}...")

        verdict = json.loads(raw_text)

        # Basic token usage (best-effort, not always available)
        token_usage = {}
        try:
            token_usage = {
                "prompt_tokens":     response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
            }
        except Exception:
            pass

        return verdict, "success", token_usage

    except json.JSONDecodeError as e:
        print(f"[gemini] JSON parse failed: {e}")
        return {}, "failed_parse", {}
    except Exception as e:
        print(f"[gemini] FAILED: {e}")
        return {}, "failed", {}


def upload_to_vercel_kv(payload: dict) -> bool:
    """Upload the final payload to Vercel KV via REST API."""
    if not KV_REST_URL or not KV_REST_TOKEN:
        print("[kv] Skipping upload — KV credentials not set.")
        return False

    url     = f"{KV_REST_URL}/set/{KV_KEY}"
    headers = {
        "Authorization": f"Bearer {KV_REST_TOKEN}",
        "Content-Type":  "application/json",
    }
    body = json.dumps(payload)

    try:
        resp = requests.post(url, headers=headers, data=json.dumps({"value": body}), timeout=10)
        resp.raise_for_status()
        print(f"[kv] Upload successful. Status: {resp.status_code}")
        return True
    except Exception as e:
        print(f"[kv] Upload FAILED: {e}")
        return False


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    start_time = time.time()
    print("=" * 60)
    print("IS KASH TILL CASHING — Agent Run Starting")
    print(f"Run ID : {GITHUB_RUN_ID}")
    print(f"Time   : {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # 1. Fetch RSS
    entries, rss_status = fetch_rss_entries()
    if not entries:
        print("[main] No RSS entries — aborting.")
        rss_status = "failed"

    # 2. Build article context
    context, sources = build_article_context(entries) if entries else ("", [])
    jina_status = "success" if any(s["url"] for s in sources) else "failed"

    # 3. Call Gemini
    verdict, llm_status, token_usage = {}, "skipped", {}
    if context:
        verdict, llm_status, token_usage = call_gemini(context)

    # 4. Assemble final payload
    execution_ms = int((time.time() - start_time) * 1000)
    overall_health = "healthy" if (rss_status == "success" and llm_status == "success") else "degraded"

    payload = {
        "metadata": {
            "schema_version":  SCHEMA_VERSION,
            "last_updated":    datetime.now(timezone.utc).isoformat(),
            "github_run_id":   GITHUB_RUN_ID,
            "execution_time_ms": execution_ms,
        },
        "system_health": {
            "status":        overall_health,
            "rss_fetch":     rss_status,
            "jina_reader":   jina_status,
            "llm_inference": llm_status,
            "token_usage":   token_usage,
        },
        "verdict":          verdict,
        "sources":          sources,
        "markets":          None,
        "tamagotchi_state": None,
    }

    print("\n[main] Final payload:")
    print(json.dumps(payload, indent=2))

    # 5. Upload to Vercel KV
    upload_to_vercel_kv(payload)

    print(f"\n[main] Done in {execution_ms}ms. Overall health: {overall_health}")
    print("=" * 60)


if __name__ == "__main__":
    main()
