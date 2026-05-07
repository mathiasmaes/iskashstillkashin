# Is Kash Till Cashing? - An Little Large Language Model playground

A playground for getting familiar with LLM and agentic AI principles, wrapped around the only question that matters: **is Kash Patel still the FBI Director?**

Twice a day, an agent wakes up, reads the news, checks the prediction markets, and delivers a confident — and deeply sassy — YES or NO.

---

## How it works

Each run scrapes Google News for Kash Patel coverage, fetches full article text via Jina.ai, and feeds it to an LLM (Gemini in CI, Ollama locally). The LLM returns a structured JSON verdict: `YES`/`NO`, confidence score, a sassy summary, and any departure details it can extract. Market odds from Kalshi and Polymarket get pulled alongside it. Everything lands in Vercel KV.

Announced departures are persisted separately and carried forward across runs — sticky until the LLM explicitly contradicts them.

Every Sunday a second script grabs the last 7 daily snapshots, computes market deltas in Python, and asks Gemini to attribute the movement — news catalyst or time decay.

---

## Deployment

The frontend is live at [iskashstillkashin.vercel.app](https://iskashstillkashin.vercel.app). `public/index.html` is the static frontend; `api/data.py` is a Python serverless function that fetches the latest payload from KV. The rewrite in `vercel.json` maps `/data` → `/api/data` so the frontend just works.

To deploy your own: add `KV_REST_API_URL` and `KV_REST_API_TOKEN` as environment variables in the Vercel dashboard, then push to `main`.

---

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in your keys

python kash.py           # run the daily agent
python kash_weekly.py    # run the weekly assessment
python serve.py          # inspect the data at localhost:8080
```

**Required env vars:**
- `GEMINI_API_KEY` — Google GenAI ([aistudio.google.com](https://aistudio.google.com), free)
- `KV_REST_API_URL` / `KV_REST_API_TOKEN` — Vercel KV
- `JINA_API_KEY` — optional, but you'll get rate-limited without it

Ollama is picked up automatically if it's running locally and `RUN_MODE` is set to `auto`.

---

## Automated runs

| Workflow | Schedule | Script |
|---|---|---|
| `daily.yml` | 08:00 UTC + 20:00 UTC daily | `kash.py` |
| `weekly.yml` | 21:00 UTC every Sunday | `kash_weekly.py` |

Both support `workflow_dispatch` for manual runs. Secrets required: `GEMINI_API_KEY`, `KV_REST_API_URL`, `KV_REST_API_TOKEN`, `JINA_API_KEY`.

---

## Future updates

- **Drunk Kash Patel tamagotchi** — 
