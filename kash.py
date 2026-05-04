import os
import json
import time
import logging
import requests
from datetime import datetime, timezone
from googlenewsdecoder import gnewsdecoder

import feedparser
from dotenv import load_dotenv

from google import genai
from google.genai import types

load_dotenv()

# --- CONFIGURATION ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
JINA_API_KEY   = os.environ.get("JINA_API_KEY", "")

KV_REST_URL    = os.environ.get("KV_REST_API_URL", "").rstrip("/")
KV_REST_TOKEN  = os.environ.get("KV_REST_API_TOKEN", "")

# --- AGENT SETTINGS ---
GEMINI_MODEL          = "gemini-flash-lite-latest"
GEMINI_MAX_RETRIES    = 5
GEMINI_RETRY_DELAY_S  = 60

# --- OLLAMA SETTINGS (local runs only) ---
# gemma3:12b fits in ~8GB of unified memory, runs Metal-accelerated on M1 Max
OLLAMA_BASE   = "http://localhost:11434"
OLLAMA_MODEL  = "gemma3:12b"

# --- RUN MODE ---
# "auto"  → use Ollama locally, Gemini on GitHub Actions (default)
# "local" → always use Ollama (force local, useful for testing without Gemini quota)
# "web"   → always use Gemini (force web, useful for comparing outputs)
RUN_MODE = "web"

RSS_FEED_URL  = "https://news.google.com/rss/search?q=Kash+Patel+FBI+Director&hl=en-US&gl=US&ceid=US:en"
JINA_BASE     = "https://r.jina.ai/"

MAX_ARTICLES       = 7
ARTICLE_CHARS      = 3000
TEMPERATURE        = 0.2
MAX_TOKENS         = 400
RUN_HISTORY_KEY    = "kash_run_history"
RUN_HISTORY_LIMIT  = 50   # entries kept in the history list

SYSTEM_PROMPT = """
You are the cynical, highly analytical, and aggressively sassy AI backend for the website "Is Kash still Kashinpyt".
Your only job is to read the provided news snippets and determine: Is Kash Patel CURRENTLY the active Director of the FBI today?

CRITICAL REASONING RULES (FOLLOW EXACTLY):

1. THE "FORMER" RULE: If credible news refers to him as the "former", "ex-", or "previous" FBI Director, the verdict is a hard "NO".
2. THE "FIRED" RULE: Only output "NO" if the text explicitly states he has ALREADY resigned, been fired, ousted, or stepped down.
3. THE "ANNOUNCEMENT" EXCEPTION: If he has announced he *will* resign or be replaced in the future, but is still in the job today, the verdict is "YES". (He's cashing those last few paychecks).
4. THE "SATIRE/ACTOR" RULE: If articles say an actor (like Aziz Ansari) is "playing", "portraying", or mocking him on TV/SNL, Kash Patel is STILL the real FBI Director. Do not confuse comedy sketches with reality.
5. THE "SURVIVOR" RULE: If the news is just about controversies, podcast interviews, partisan outrage, or terrible press, and there's no further indication in the other rules, the verdict is "YES". He is still clinging to power. Let your sassy summary reflect how he somehow survived another news cycle despite the chaos.

Return ONLY valid JSON matching this exact schema:
{
  "verdict": "YES" or "NO",
  "confidence": <float between 0.0 and 1.0>,
  "summary": "<Sassy, cynical 2-3 sentence summary. If YES, mock how he is still surviving the chaos or cashing checks. If NO, joke about the inevitable finally happening. You can definitely use any content you just read to make sassy comments. Max 100 words.>",
  "reason": "<A serious, literal 1-sentence explanation of your verdict based on the text.>"
}
"""

# ---------------------------------------------------------------------------
# LOGGING SETUP
# ---------------------------------------------------------------------------

class _UTCFormatter(logging.Formatter):
    converter = time.gmtime  # force UTC in all timestamps

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

# Component loggers — each maps to a functional area for easy filtering/grepping
log_rss     = logging.getLogger("rss")
log_resolve = logging.getLogger("resolve")
log_jina    = logging.getLogger("jina")
log_ollama  = logging.getLogger("ollama")
log_gemini  = logging.getLogger("gemini")
log_kv      = logging.getLogger("kv")
log_main    = logging.getLogger("main")

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def is_local_run() -> bool:
    return not os.environ.get("GITHUB_RUN_ID")

def ollama_available() -> bool:
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False

def _kv_headers() -> dict:
    return {
        "Authorization": f"Bearer {KV_REST_TOKEN}",
        "Content-Type":  "application/json",
    }

# ---------------------------------------------------------------------------
# RSS + URL RESOLUTION
# ---------------------------------------------------------------------------

def fetch_rss_articles() -> list[dict]:
    log_rss.info(f"Fetching feed  url={RSS_FEED_URL}")
    feed = feedparser.parse(RSS_FEED_URL)
    articles = []
    for entry in feed.entries[:MAX_ARTICLES]:
        articles.append({
            "title":     entry.title,
            "link":      entry.link,
            "published": entry.published,
        })
    log_rss.info(f"Fetched {len(articles)} articles")
    return articles

def resolve_url(url: str) -> str:
    if "news.google.com/rss/articles/" not in url:
        return url
    try:
        decoded = gnewsdecoder(url)
        if decoded.get("status"):
            real_url = decoded["decoded_url"]
            log_resolve.debug(f"Decoded  url={real_url[:80]}")
            return real_url
        log_resolve.warning(f"Decoder error  msg={decoded.get('message')}  url={url[:60]}")
        return url
    except Exception as e:
        log_resolve.error(f"Decode failed  error={e}  url={url[:60]}")
        return url

# ---------------------------------------------------------------------------
# JINA READER
# ---------------------------------------------------------------------------

def read_article_via_jina(url: str) -> str:
    jina_url = f"{JINA_BASE}{url}"
    headers = {
        "Accept":                "application/json",
        "X-No-Cache":            "true",
        "X-Remove-Images":       "true",
        "X-With-Links-Summary":  "none",
        "X-With-Images-Summary": "none",
        "X-Return-Format":       "text",
    }
    if JINA_API_KEY:
        headers["Authorization"] = f"Bearer {JINA_API_KEY}"
    try:
        resp = requests.get(jina_url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("data", {}).get("content", resp.text)
        text = text[:ARTICLE_CHARS]
        log_jina.info(f"OK  chars={len(text)}  url={url[:70]}")
        return text
    except Exception as e:
        log_jina.warning(f"FAILED — will use RSS snippet  error={e}  url={url[:70]}")
        return ""

# ---------------------------------------------------------------------------
# LLM CALLERS
# ---------------------------------------------------------------------------

def call_ollama(context: str) -> tuple[dict, str, dict]:
    user_message = (
        "Here are the latest news articles about Kash Patel. "
        "Analyze them and return your JSON verdict.\n\n" + context
    )
    try:
        log_ollama.info(f"Calling model  model={OLLAMA_MODEL}  context_chars={len(context)}")
        resp = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={
                "model":   OLLAMA_MODEL,
                "prompt":  user_message,
                "system":  SYSTEM_PROMPT,
                "stream":  False,
                "format":  "json",
                "options": {"temperature": TEMPERATURE, "num_predict": MAX_TOKENS},
            },
            timeout=120,
        )
        resp.raise_for_status()
        body = resp.json()
        raw = body.get("response", "")
        if not raw:
            log_ollama.error("Empty response from model")
            return {}, "failed", {}
        verdict = json.loads(raw)
        token_usage = {
            "prompt_tokens":     body.get("prompt_eval_count", 0),
            "completion_tokens": body.get("eval_count", 0),
        }
        log_ollama.info(
            f"OK  verdict={verdict.get('verdict')}  confidence={verdict.get('confidence')}"
            f"  tokens_in={token_usage['prompt_tokens']}  tokens_out={token_usage['completion_tokens']}"
        )
        return verdict, "success", token_usage
    except json.JSONDecodeError as e:
        log_ollama.error(f"JSON parse failed  error={e}")
        return {}, "failed_parse", {}
    except Exception as e:
        log_ollama.error(f"Request failed  error={e}")
        return {}, "failed", {}

_GEMINI_RETRYABLE_SIGNALS = ("429", "503", "resourceexhausted", "overloaded", "serviceunavailable")

def _is_retryable_gemini_error(e: Exception) -> bool:
    lowered = str(e).lower()
    return any(sig in lowered for sig in _GEMINI_RETRYABLE_SIGNALS)

def call_gemini(context: str) -> tuple[dict, str, dict]:
    if not GEMINI_API_KEY:
        log_gemini.warning("GEMINI_API_KEY not set — skipping")
        return {}, "skipped", {}

    client = genai.Client(api_key=GEMINI_API_KEY)
    user_message = (
        "Here are the latest news articles about Kash Patel. "
        "Analyze them and return your JSON verdict.\n\n" + context
    )
    log_gemini.info(f"Calling model  model={GEMINI_MODEL}  context_chars={len(context)}")

    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=TEMPERATURE,
                    max_output_tokens=MAX_TOKENS,
                    response_mime_type="application/json",
                ),
            )
            verdict = json.loads(response.text)
            token_usage = {}
            try:
                token_usage = {
                    "prompt_tokens":     response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                }
            except Exception:
                pass
            log_gemini.info(
                f"OK  attempt={attempt}/{GEMINI_MAX_RETRIES}  verdict={verdict.get('verdict')}"
                f"  confidence={verdict.get('confidence')}"
                f"  tokens_in={token_usage.get('prompt_tokens', '?')}"
                f"  tokens_out={token_usage.get('completion_tokens', '?')}"
            )
            return verdict, "success", token_usage
        except json.JSONDecodeError as e:
            log_gemini.error(f"JSON parse failed  attempt={attempt}/{GEMINI_MAX_RETRIES}  error={e}")
            return {}, "failed_parse", {}
        except Exception as e:
            if _is_retryable_gemini_error(e):
                if attempt < GEMINI_MAX_RETRIES:
                    log_gemini.warning(
                        f"Rate-limited or overloaded — will retry"
                        f"  attempt={attempt}/{GEMINI_MAX_RETRIES}"
                        f"  wait_s={GEMINI_RETRY_DELAY_S}  error={e}"
                    )
                    time.sleep(GEMINI_RETRY_DELAY_S)
                else:
                    log_gemini.error(
                        f"Gemini exhausted after {GEMINI_MAX_RETRIES} retries — giving up  error={e}"
                    )
                    return {}, "failed_rate_limit", {}
            else:
                log_gemini.error(f"Request failed (non-retryable)  attempt={attempt}/{GEMINI_MAX_RETRIES}  error={e}")
                return {}, "failed", {}

    return {}, "failed_rate_limit", {}

# ---------------------------------------------------------------------------
# KV STORE
# ---------------------------------------------------------------------------

def load_cached_data(date_str: str) -> tuple[str, list] | tuple[None, None]:
    if not KV_REST_URL or not KV_REST_TOKEN:
        return None, None
    try:
        resp = requests.get(
            f"{KV_REST_URL}/get/kash_articles_{date_str}",
            headers=_kv_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json().get("result")
        if result:
            data = json.loads(result)
            # Recover from old malformed saves that stored ["json_str", "EX", ttl]
            if isinstance(data, list):
                data = json.loads(data[0])
            log_kv.info(f"Cache HIT  date={date_str}  articles={len(data['articles'])}")
            return data["context"], data["articles"]
        log_kv.info(f"Cache MISS  date={date_str}")
    except Exception as e:
        log_kv.error(f"Cache load failed  error={e}")
    return None, None

def save_cached_data(date_str: str, context: str, articles: list):
    if not KV_REST_URL or not KV_REST_TOKEN:
        return
    try:
        key = f"kash_articles_{date_str}"
        payload_str = json.dumps({"context": context, "articles": articles})
        resp = requests.post(
            f"{KV_REST_URL}/set/{key}",
            headers=_kv_headers(),
            json=payload_str,
            timeout=10,
        )
        resp.raise_for_status()
        # TTL via separate EXPIRE — Upstash REST treats the body as the literal value
        requests.post(f"{KV_REST_URL}/expire/{key}/93600", headers=_kv_headers(), timeout=5)
        log_kv.info(f"Cache saved  date={date_str}  articles={len(articles)}  ttl=26h")
    except Exception as e:
        log_kv.error(f"Cache save failed  error={e}")

def upload_to_vercel_kv(payload: dict):
    if not KV_REST_URL or not KV_REST_TOKEN:
        log_kv.warning("KV credentials missing — skipping status upload")
        return
    try:
        resp = requests.post(
            f"{KV_REST_URL}/set/kash_status_latest",
            headers=_kv_headers(),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        log_kv.info("Status latest written  key=kash_status_latest")
    except Exception as e:
        log_kv.error(f"Status upload failed  error={e}")

def append_run_history(summary: dict):
    """Prepend a compact run summary to the history list; keep last RUN_HISTORY_LIMIT entries."""
    if not KV_REST_URL or not KV_REST_TOKEN:
        log_kv.warning("KV credentials missing — skipping history append")
        return
    try:
        entry = json.dumps(summary)
        resp = requests.post(
            f"{KV_REST_URL}/pipeline",
            headers=_kv_headers(),
            json=[
                ["LPUSH", RUN_HISTORY_KEY, entry],
                ["LTRIM", RUN_HISTORY_KEY, 0, RUN_HISTORY_LIMIT - 1],
            ],
            timeout=10,
        )
        resp.raise_for_status()
        log_kv.info(f"Run history appended  key={RUN_HISTORY_KEY}  limit={RUN_HISTORY_LIMIT}")
    except Exception as e:
        log_kv.error(f"Run history append failed  error={e}")

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    setup_logging()
    start_time = time.time()

    run_id  = os.environ.get("GITHUB_RUN_ID", "local")
    now_str = datetime.now(timezone.utc).isoformat()
    today   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    log_main.info("=" * 56)
    log_main.info(f"Agent run starting  run_id={run_id}  mode={RUN_MODE}  date={today}")
    log_main.info("=" * 56)

    # 1. Try cache — skip RSS + Jina entirely if we already fetched today
    full_context, articles = load_cached_data(today)
    articles    = articles or []
    jina_status = "cached"
    cache_hit   = bool(full_context)

    if cache_hit:
        log_main.info(f"Cache hit — skipping all fetching  date={today}")
    else:
        # 1b. Fetch RSS
        articles = fetch_rss_articles()

        # 2. Read each article via Jina
        context_blocks = []
        jina_successes = 0

        for i, art in enumerate(articles, 1):
            log_main.info(f"Processing article  {i}/{len(articles)}  title={art['title'][:60]}")
            real_url = resolve_url(art["link"])
            content  = read_article_via_jina(real_url)

            if not content:
                log_jina.warning(f"Fallback to RSS snippet  article={i}/{len(articles)}  url={real_url[:70]}")
                content = f"Title: {art['title']}\nSummary: {art.get('description', 'No snippet available')}"
            else:
                jina_successes += 1

            context_blocks.append(
                f"--- ARTICLE {i} ---\nTitle: {art['title']}\nPublished: {art['published']}\nContent:\n{content}\n"
            )

        full_context = "\n".join(context_blocks)
        log_jina.info(f"Fetch complete  successes={jina_successes}/{len(articles)}")

        if jina_successes >= 2:
            jina_status = "success"
        elif jina_successes == 0:
            jina_status = "failed"
        else:
            jina_status = "degraded"

        if full_context.strip() and jina_successes >= 1:
            save_cached_data(today, full_context, articles)

    # 3. Call LLM
    verdict_data, llm_status, token_usage = {}, "skipped", {}
    llm_provider = "none"

    if not full_context or not full_context.strip():
        log_main.error("No article context gathered — skipping LLM call")
        jina_status = "failed"
    else:
        use_local = (
            RUN_MODE == "local"
            or (RUN_MODE == "auto" and is_local_run() and ollama_available())
        )
        if use_local:
            llm_provider = "ollama"
            log_main.info(f"LLM selected  provider=ollama  model={OLLAMA_MODEL}  run_mode={RUN_MODE}")
            verdict_data, llm_status, token_usage = call_ollama(full_context)
            if llm_status != "success" and RUN_MODE == "auto":
                log_main.warning("Ollama failed — falling back to Gemini")
                llm_provider = "gemini"
                verdict_data, llm_status, token_usage = call_gemini(full_context)
        else:
            llm_provider = "gemini"
            log_main.info(f"LLM selected  provider=gemini  model={GEMINI_MODEL}  run_mode={RUN_MODE}")
            verdict_data, llm_status, token_usage = call_gemini(full_context)

    elapsed_ms = int((time.time() - start_time) * 1000)
    overall_health = "healthy" if (jina_status in ("success", "cached") and llm_status == "success") else "degraded"

    # 4. Assemble payload
    payload = {
        "metadata": {
            "schema_version": "1.0",
            "last_updated":   now_str,
            "github_run_id":  run_id,
            "execution_time_ms": elapsed_ms,
        },
        "system_health": {
            "status":       overall_health,
            "rss_fetch":    "success" if articles else "failed",
            "jina_reader":  jina_status,
            "llm_inference": llm_status,
            "llm_provider": llm_provider,
            "token_usage":  token_usage,
        },
        "verdict": verdict_data,
        "sources": [
            {"title": a["title"], "url": a["link"], "published_at": a["published"]}
            for a in articles
        ],
        "markets":         None,
        "tamagotchi_state": None,
    }

    log_main.info(f"\n{json.dumps(payload, indent=2)}")

    # 5. Upload status + run history
    upload_to_vercel_kv(payload)

    run_summary = {
        "run_id":           run_id,
        "timestamp":        now_str,
        "run_mode":         RUN_MODE,
        "cache_hit":        cache_hit,
        "articles_total":   len(articles),
        "jina_successes":   0 if cache_hit else jina_successes if not cache_hit else None,
        "jina_status":      jina_status,
        "llm_provider":     llm_provider,
        "llm_model":        OLLAMA_MODEL if llm_provider == "ollama" else GEMINI_MODEL,
        "llm_status":       llm_status,
        "verdict":          verdict_data.get("verdict"),
        "confidence":       verdict_data.get("confidence"),
        "token_usage":      token_usage,
        "execution_time_ms": elapsed_ms,
        "overall_health":   overall_health,
    }
    append_run_history(run_summary)

    log_main.info("=" * 56)
    log_main.info(
        f"Run complete  verdict={verdict_data.get('verdict')}  health={overall_health}"
        f"  elapsed={elapsed_ms}ms  run_id={run_id}"
    )
    log_main.info("=" * 56)

if __name__ == "__main__":
    main()
