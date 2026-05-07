#!/usr/bin/env python3
"""Minimal dev server — fetches kash_status_latest + kash_weekly_assessment from KV.
Usage: python serve.py   (then open http://localhost:8080)
"""
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

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
KV_REST_URL   = os.environ.get("KV_REST_API_URL", "").rstrip("/")
KV_REST_TOKEN = os.environ.get("KV_REST_API_TOKEN", "")
PORT = 8080

# ---------------------------------------------------------------------------
# HTML (single page, no framework, no build step)
# ---------------------------------------------------------------------------
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Is Kash Still Kashin?</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 2rem; max-width: 900px; margin: 0 auto; }
  h1 { font-size: 1.1rem; font-weight: 500; color: #888; margin-bottom: 2rem; letter-spacing: .05em; text-transform: uppercase; }

  .card {
    background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: .75rem;
    padding: 1.25rem 1.5rem; margin-bottom: 1rem;
  }
  .card h2 { font-size: .7rem; font-weight: 600; color: #666; text-transform: uppercase; letter-spacing: .1em; margin-bottom: .75rem; }
  .card p, .card li { font-size: .95rem; line-height: 1.6; color: #ccc; }
  .card ul { padding-left: 1.2rem; }

  /* Verdict card */
  .verdict-card.yes     { background: linear-gradient(135deg, #071510 0%, #0d2b1a 100%); border-color: #14532d; }
  .verdict-card.no      { background: linear-gradient(135deg, #170808 0%, #2a0d0d 100%); border-color: #7f1d1d; }
  .verdict-card.unknown { background: #1a1a1a; border-color: #2a2a2a; }

  .verdict-layout {
    display: grid; grid-template-columns: auto 1fr; gap: 2rem; align-items: center;
  }
  @media (max-width: 560px) { .verdict-layout { grid-template-columns: 1fr; gap: 1rem; } }

  .verdict-word { font-size: 8rem; font-weight: 900; line-height: 1; letter-spacing: -.04em; }
  .vc-yes { color: #4ade80; }
  .vc-no  { color: #f87171; }
  .vc-unk { color: #a8a29e; }

  .verdict-summary { font-size: 1rem; line-height: 1.65; color: #d4d4d4; margin-bottom: .6rem; }
  .verdict-reason  { font-size: .85rem; color: #888; font-style: italic; line-height: 1.5; }

  /* Markets grid */
  .markets-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }
  @media (max-width: 600px) { .markets-grid { grid-template-columns: 1fr; } }

  .market-card {
    background: #141414; border: 1px solid #222; border-radius: .75rem;
    padding: 1.25rem; display: flex; flex-direction: column; gap: .75rem;
  }
  .market-header { display: flex; justify-content: space-between; align-items: flex-start; gap: .5rem; }
  .market-badge {
    font-size: .65rem; font-weight: 700; letter-spacing: .08em;
    text-transform: uppercase; padding: .2rem .55rem; border-radius: 999px; white-space: nowrap;
  }
  .badge-pm    { background: rgba(86,193,255,.15); color: #56c1ff; border: 1px solid rgba(86,193,255,.3); }
  .badge-kal   { background: rgba(40,204,149,.15); color: #28cc95; border: 1px solid rgba(40,204,149,.3); }
  .market-question { font-size: .8rem; color: #aaa; flex: 1; }

  .market-prob { font-size: 2.6rem; font-weight: 800; letter-spacing: -.03em; line-height: 1; }
  .prob-pm  { color: #56c1ff; }
  .prob-kal { color: #28cc95; }

  .prob-bar { height: 5px; background: #2a2a2a; border-radius: 3px; }
  .prob-fill-pm  { height: 100%; border-radius: 3px; background: #56c1ff; transition: width .4s; }
  .prob-fill-kal { height: 100%; border-radius: 3px; background: #28cc95; transition: width .4s; }

  .market-meta { display: flex; gap: 1rem; flex-wrap: wrap; }
  .market-meta-item { font-size: .72rem; color: #555; }
  .market-meta-item span { color: #888; }

  .market-footer { margin-top: auto; padding-top: .5rem; border-top: 1px solid #222; display: flex; justify-content: space-between; align-items: center; }
  .market-link { font-size: .72rem; color: #555; text-decoration: none; }
  .market-link:hover { color: #888; text-decoration: underline; }

  /* Timelines dropdown */
  .timelines-toggle {
    background: none; border: none; color: #555; font-size: .72rem; cursor: pointer;
    padding: 0; display: flex; align-items: center; gap: .25rem;
  }
  .timelines-toggle:hover { color: #888; }
  .timelines-panel { display: none; margin-top: .75rem; border-top: 1px solid #1e1e1e; padding-top: .75rem; }
  .timelines-panel.open { display: block; }
  .timeline-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: .3rem 0; border-bottom: 1px solid #1a1a1a; gap: .5rem;
  }
  .timeline-row:last-child { border-bottom: none; }
  .timeline-label { font-size: .78rem; color: #888; }
  .timeline-right { display: flex; align-items: center; gap: .5rem; }
  .timeline-prob { font-size: .82rem; font-weight: 600; color: #ccc; }
  .timeline-status { font-size: .65rem; color: #555; }

  /* Shared utilities */
  .meta-row { display: flex; gap: 1.5rem; flex-wrap: wrap; }
  .meta-item { font-size: .8rem; color: #666; }
  .meta-item span { color: #aaa; }

  .pill { display: inline-block; padding: .2rem .6rem; border-radius: 999px; font-size: .72rem; font-weight: 600; letter-spacing: .04em; }
  .pill-green { background: #14532d; color: #4ade80; }
  .pill-red   { background: #450a0a; color: #f87171; }
  .pill-amber { background: #451a03; color: #fb923c; }
  .pill-grey  { background: #1c1917; color: #a8a29e; }

  .confidence-bar { height: 6px; background: #2a2a2a; border-radius: 3px; margin-top: .5rem; }
  .confidence-fill { height: 100%; border-radius: 3px; background: #4ade80; transition: width .4s; }

  a { color: #60a5fa; text-decoration: none; }
  a:hover { text-decoration: underline; }

  #error { color: #f87171; padding: 1rem; border: 1px solid #450a0a; border-radius: .5rem; display: none; }
  #loading { color: #666; font-size: .9rem; }
</style>
</head>
<body>

<h1>Is Kash Still Kashin? &mdash; Data Inspector</h1>
<p id="loading">Fetching latest data&hellip;</p>
<p id="error"></p>
<div id="app" style="display:none"></div>

<script>
async function load() {
  const loading = document.getElementById('loading');
  const errEl   = document.getElementById('error');
  const app     = document.getElementById('app');
  try {
    const r = await fetch('/data');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    loading.style.display = 'none';
    app.style.display = 'block';
    render(d, app);
  } catch (e) {
    loading.style.display = 'none';
    errEl.style.display = 'block';
    errEl.textContent = 'Failed to load data: ' + e.message;
  }
}

function pill(text, cls) { return `<span class="pill ${cls}">${text}</span>`; }

function healthPill(val) {
  if (val === 'success' || val === 'healthy' || val === 'cached') return pill(val, 'pill-green');
  if (val === 'degraded') return pill(val, 'pill-amber');
  if (val === 'failed')   return pill(val, 'pill-red');
  return pill(val ?? 'unknown', 'pill-grey');
}

function fmtVol(v) {
  if (v == null) return '—';
  if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
  if (v >= 1e3) return '$' + (v / 1e3).toFixed(0) + 'k';
  return '$' + Math.round(v);
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function marketCard(source, data) {
  if (!data || !data.primary) return '';
  const p   = data.primary;
  const all = data.all_markets ?? [];
  const isPM    = source === 'polymarket';
  const badge   = isPM ? 'badge-pm'       : 'badge-kal';
  const probCls = isPM ? 'prob-pm'         : 'prob-kal';
  const fillCls = isPM ? 'prob-fill-pm'    : 'prob-fill-kal';
  const label   = isPM ? 'Polymarket'      : 'Kalshi';
  const pct     = Math.round((p.probability_yes ?? 0) * 100);

  let deltaBadge = '';
  if (p.prev_probability_yes != null) {
    const delta = Math.round((p.probability_yes - p.prev_probability_yes) * 100);
    if (delta !== 0) {
      const sign  = delta > 0 ? '+' : '';
      const color = delta > 0 ? '#f87171' : '#4ade80';
      deltaBadge = `<span style="font-size:.75rem; color:${color}; margin-left:.4rem">${sign}${delta}pp</span>`;
    }
  }

  const id     = `tl-${source}`;
  const others = all.filter(m => m.id !== p.id);
  let timelinesHtml = '';
  if (others.length) {
    const rows = others.map(m => {
      const mpct        = Math.round((m.probability_yes ?? 0) * 100);
      const statusLabel = m.status === 'resolved'
        ? (m.outcome ? `Resolved ${m.outcome.toUpperCase()}` : 'Resolved')
        : fmtDate(m.deadline);
      return `<div class="timeline-row">
        <span class="timeline-label">${m.question ?? m.deadline ?? '—'}</span>
        <div class="timeline-right">
          <span class="timeline-prob">${m.status === 'resolved' && m.outcome ? (m.outcome === 'yes' ? '✓ Yes' : '✗ No') : mpct + '%'}</span>
          <span class="timeline-status">${statusLabel}</span>
        </div>
      </div>`;
    }).join('');
    timelinesHtml = `
      <div>
        <button class="timelines-toggle" onclick="toggleTimelines('${id}')">
          <span id="${id}-arrow">▸</span> ${others.length} more timeline${others.length > 1 ? 's' : ''}
        </button>
        <div id="${id}" class="timelines-panel">${rows}</div>
      </div>`;
  }

  return `<div class="market-card">
    <div class="market-header">
      <span class="market-question">Will Kash Patel leave as FBI Director?</span>
      <span class="market-badge ${badge}">${label}</span>
    </div>
    <div>
      <div style="display:flex; align-items:baseline; gap:.25rem">
        <span class="market-prob ${probCls}">${pct}%</span>
        <span style="font-size:.8rem; color:#555">YES${deltaBadge}</span>
      </div>
      <div class="prob-bar" style="margin-top:.4rem">
        <div class="${fillCls}" style="width:${pct}%"></div>
      </div>
    </div>
    <div class="market-meta">
      <div class="market-meta-item">Deadline <span>${fmtDate(p.deadline)}</span></div>
      <div class="market-meta-item">Volume <span>${fmtVol(p.volume_total)}</span></div>
      ${p.volume_24h != null ? `<div class="market-meta-item">24h vol <span>${fmtVol(p.volume_24h)}</span></div>` : ''}
    </div>
    ${timelinesHtml}
    <div class="market-footer">
      <a href="${p.url}" target="_blank" rel="noopener" class="market-link">View on ${label} ↗</a>
      <span style="font-size:.65rem; color:#333">${p.id ?? ''}</span>
    </div>
  </div>`;
}

function toggleTimelines(id) {
  const panel = document.getElementById(id);
  const arrow = document.getElementById(id + '-arrow');
  const open  = panel.classList.toggle('open');
  arrow.textContent = open ? '▾' : '▸';
}

function render(d, root) {
  const v       = d.verdict          ?? {};
  const dep     = d.departure_info   ?? {};
  const meta    = d.metadata         ?? {};
  const health  = d.system_health    ?? {};
  const sources = d.sources          ?? [];
  const markets = d.markets          ?? {};
  const wa      = d.weekly_assessment ?? null;

  const verdict    = v.verdict ?? 'UNKNOWN';
  const bannerCls  = verdict === 'YES' ? 'yes' : verdict === 'NO' ? 'no' : 'unknown';
  const vcCls      = verdict === 'YES' ? 'vc-yes' : verdict === 'NO' ? 'vc-no' : 'vc-unk';
  const confidence = v.confidence ?? 0;
  const pct        = Math.round(confidence * 100);
  const updatedAt  = meta.last_updated ? new Date(meta.last_updated).toLocaleString() : '—';

  // 1. Verdict banner — big YES/NO + summary + reason + confidence
  let html = `
    <div class="card verdict-card ${bannerCls}" style="padding:1.75rem 2rem">
      <div class="verdict-layout">
        <div class="verdict-word ${vcCls}">${verdict}</div>
        <div class="verdict-body">
          <p class="verdict-summary">${v.summary ?? '—'}</p>
          <p class="verdict-reason" style="margin-top:.5rem">${v.reason ?? ''}</p>
          <div class="confidence-bar" style="margin-top:.9rem">
            <div class="confidence-fill" style="width:${pct}%"></div>
          </div>
          <p style="font-size:.75rem; color:#555; margin-top:.3rem">Confidence: ${pct}%</p>
        </div>
      </div>
    </div>`;

  // 2. Departure — always shown
  const depBorderColor = dep.announced ? '#78350f' : '#14532d33';
  let depBody = '';
  if (dep.announced) {
    depBody = `<ul>
      ${dep.departure_date     ? `<li>Departure date: <strong>${dep.departure_date}</strong></li>` : '<li style="color:#888"><em>Departure date not yet specified</em></li>'}
      ${dep.announced_by       ? `<li>Announced by: <strong>${dep.announced_by}</strong></li>` : ''}
      ${dep.announcement_date  ? `<li>Announced on: <strong>${dep.announcement_date}</strong></li>` : ''}
      ${dep.announcement_summary ? `<li>${dep.announcement_summary}</li>` : ''}
    </ul>`;
  } else {
    depBody = `<p style="color:#4ade80; font-size:.9rem">No departure announced — still cashing those federal paychecks.</p>`;
  }
  html += `
    <div class="card" style="border-color:${depBorderColor}">
      <h2>${dep.announced ? '&#9888; Departure Announced' : 'Departure Status'}</h2>
      ${depBody}
    </div>`;

  // 3. Prediction markets + Weekly pulse — one combined unit
  const pmCard  = marketCard('polymarket', markets.polymarket);
  const kalCard = marketCard('kalshi',     markets.kalshi);

  let weeklySection = '';
  if (wa && (wa.price_summary || wa.weekly_take)) {
    const driverColors = { news: '#f59e0b', time_decay: '#60a5fa', mixed: '#a78bfa', unclear: '#6b7280' };
    const driverColor  = driverColors[wa.driver] || '#6b7280';
    const dirArrow     = wa.direction === 'up' ? '↑' : wa.direction === 'down' ? '↓' : '→';
    const dirColor     = wa.direction === 'up' ? '#f87171' : wa.direction === 'down' ? '#4ade80' : '#888';
    weeklySection = `
      <div style="border-top:1px solid #222; margin-top:1.25rem; padding-top:1.25rem">
        <h2 style="margin-bottom:.75rem">Weekly Market Pulse${wa.week_of ? ' &mdash; w/o ' + wa.week_of : ''}</h2>
        <p style="font-size:.82rem; color:#555; font-family:monospace; margin-bottom:.75rem; line-height:1.5">${wa.price_summary ?? ''}</p>
        <p style="font-size:.95rem; color:#ccc; line-height:1.65; margin-bottom:.6rem">${wa.weekly_take ?? ''}</p>
        <p style="font-size:.83rem; color:#888; font-style:italic; line-height:1.5">${wa.driver_summary ?? ''}</p>
        <div class="meta-row" style="margin-top:.8rem">
          <div class="meta-item">Driver <span style="color:${driverColor}">${wa.driver ?? '—'}</span></div>
          <div class="meta-item">Direction <span style="color:${dirColor}">${dirArrow} ${wa.direction ?? '—'}</span></div>
          ${wa.markets_agree != null ? `<div class="meta-item">Markets agree <span>${wa.markets_agree ? 'Yes' : 'No'}</span></div>` : ''}
          ${wa.snapshots_used != null ? `<div class="meta-item">Days used <span>${wa.snapshots_used}</span></div>` : ''}
        </div>
      </div>`;
  } else {
    weeklySection = `
      <div style="border-top:1px solid #222; margin-top:1.25rem; padding-top:1.25rem; opacity:.4">
        <h2 style="margin-bottom:.5rem">Weekly Market Pulse</h2>
        <p style="font-size:.85rem; color:#666; line-height:1.6">
          Pending — collects one snapshot per day and generates every Sunday.<br>
          Run <code style="font-size:.8rem; color:#888">python kash_weekly.py</code> to generate from available snapshots.
        </p>
      </div>`;
  }

  if (pmCard || kalCard) {
    html += `
    <div class="card" style="padding:1.25rem">
      <h2>Prediction Markets</h2>
      <div class="markets-grid">
        ${pmCard}
        ${kalCard}
      </div>
      ${weeklySection}
    </div>`;
  }

  // 5. System health
  const tokens = health.token_usage ?? {};
  html += `
    <div class="card">
      <h2>System Health</h2>
      <div class="meta-row" style="margin-bottom:.75rem">
        <div class="meta-item">Status ${healthPill(health.status)}</div>
        <div class="meta-item">RSS ${healthPill(health.rss_fetch)}</div>
        <div class="meta-item">Jina ${healthPill(health.jina_reader)}</div>
        <div class="meta-item">LLM ${healthPill(health.llm_inference)}</div>
      </div>
      <div class="meta-row">
        <div class="meta-item">Provider <span>${health.llm_provider ?? '—'}</span></div>
        <div class="meta-item">Tokens in <span>${tokens.prompt_tokens ?? '—'}</span></div>
        <div class="meta-item">Tokens out <span>${tokens.completion_tokens ?? '—'}</span></div>
        <div class="meta-item">Run time <span>${meta.execution_time_ms ? meta.execution_time_ms + ' ms' : '—'}</span></div>
        <div class="meta-item">Run ID <span>${meta.github_run_id ?? '—'}</span></div>
      </div>
    </div>`;

  // 6. Sources
  if (sources.length) {
    const rows = sources.map(s =>
      `<li><a href="${s.url}" target="_blank" rel="noopener">${s.title}</a>
       <span style="color:#555; font-size:.8rem"> &mdash; ${s.published_at ?? ''}</span></li>`
    ).join('');
    html += `
    <div class="card">
      <h2>Sources (${sources.length})</h2>
      <ul style="padding-left:1.2rem">${rows}</ul>
    </div>`;
  }

  html += `<p style="font-size:.75rem; color:#444; margin-top:1rem">Last updated: ${updatedAt}</p>`;
  root.innerHTML = html;
}

load();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

def _kv_get(key: str):
    """Fetch a single key from Vercel KV. Returns parsed Python object or None."""
    req = urllib.request.Request(
        f"{KV_REST_URL}/get/{key}",
        headers={"Authorization": f"Bearer {KV_REST_TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        envelope = json.loads(resp.read())
    result = envelope.get("result")
    if result is None:
        return None
    return json.loads(result) if isinstance(result, str) else result


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self._send(200, "text/html", HTML.encode())
        elif self.path == "/data":
            self._send_data()
        else:
            self._send(404, "text/plain", b"not found")

    def _send_data(self):
        if not KV_REST_URL or not KV_REST_TOKEN:
            body = json.dumps({"error": "KV credentials not set in .env"}).encode()
            self._send(500, "application/json", body)
            return
        try:
            data = _kv_get("kash_status_latest") or {}
        except Exception as e:
            body = json.dumps({"error": str(e)}).encode()
            self._send(500, "application/json", body)
            return

        # Attach weekly assessment if available (optional — silently skip on failure)
        try:
            weekly = _kv_get("kash_weekly_assessment")
            if weekly:
                data["weekly_assessment"] = weekly
        except Exception:
            pass

        self._send(200, "application/json", json.dumps(data).encode())

    def _send(self, code, content_type, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # silence request noise


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HTTPServer.allow_reuse_address = True
    print(f"http://localhost:{PORT}")
    HTTPServer(("", PORT), Handler).serve_forever()
