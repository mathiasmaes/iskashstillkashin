import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler

KV_REST_URL   = os.environ.get("KV_REST_API_URL", "").rstrip("/")
KV_REST_TOKEN = os.environ.get("KV_REST_API_TOKEN", "")


def _kv_get(key: str):
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


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not KV_REST_URL or not KV_REST_TOKEN:
            self._send(500, {"error": "KV credentials not configured"})
            return
        try:
            data = _kv_get("kash_status_latest") or {}
        except Exception as e:
            self._send(500, {"error": str(e)})
            return

        try:
            weekly = _kv_get("kash_weekly_assessment")
            if weekly:
                data["weekly_assessment"] = weekly
        except Exception:
            pass

        self._send(200, data)

    def _send(self, code: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        pass
