from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DEFAULT_LIMIT = 25
MAX_LIMIT = 100
_CACHE_LOCK = threading.Lock()
_LAKE_CACHE: list[dict[str, Any]] = []
_LAKE_CACHE_ERROR: str | None = None
_LAKE_CACHE_REFRESHED_AT: float | None = None


def _load_dotenv() -> None:
    """Load a local .env for developer proxy tests without printing values."""

    candidates: list[Path] = []
    explicit = os.getenv("DLM_PROXY_ENV_FILE")
    if explicit:
        candidates.append(Path(explicit))

    cwd = Path.cwd()
    candidates.extend([cwd / ".env", *[parent / ".env" for parent in cwd.parents]])
    script_root = Path(__file__).resolve().parent
    candidates.extend([script_root / ".env", *[parent / ".env" for parent in script_root.parents]])

    for path in candidates:
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        return


def _dlm_json(path: str) -> dict[str, Any]:
    base_url = (os.getenv("DLM_API_BASE_URL") or os.getenv("DLM_BASE_URL") or "http://127.0.0.1:9001").rstrip("/")
    auth_header = os.getenv("DLM_API_KEY_HEADER") or os.getenv("DLM_CORE_API_KEY_HEADER") or "X-Report-Key"
    auth_value = os.getenv("DLM_API_TOKEN") or os.getenv("DLM_API_KEY") or os.getenv("DLM_CORE_API_KEY") or os.getenv("DLM_REPORT_KEY")
    client_id = os.getenv("DLM_CLIENT_ID") or os.getenv("OBS_CLIENT_ID") or "1"

    if not auth_value:
        raise RuntimeError("missing DLM API token env")

    request = urllib.request.Request(
        f"{base_url}{path}",
        headers={
            "Accept": "application/json",
            "X-Client-Id": client_id,
            "X-DLM-Source-App": "abstract_mcp_dlm_local_proxy",
            auth_header: auth_value,
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"DLM API returned HTTP {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError("DLM API request failed") from exc

    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError("DLM API returned invalid JSON") from exc

    if not isinstance(decoded, dict):
        raise RuntimeError("DLM API returned unexpected payload")
    return decoded


def _normalize_lake(item: dict[str, Any]) -> dict[str, Any]:
    lake_id = str(item.get("lake_id") or item.get("id") or "").strip()
    name = str(item.get("name") or lake_id).strip()
    status = str(item.get("status") or "unknown").strip()
    year = str(item.get("year") or item.get("created_year") or "2026").strip()

    return {
        "title": name or lake_id or "DLM lake",
        "identifier": lake_id,
        "external_id": lake_id,
        "lake_id": lake_id,
        "name": name or lake_id,
        "status": status,
        "date": year,
        "year": year,
        "source": "dlm_core.lake_configuration_context",
    }


def refresh_lake_cache() -> tuple[int, str | None]:
    """Fetch lake metadata outside the Core runtime operation request."""

    global _LAKE_CACHE, _LAKE_CACHE_ERROR, _LAKE_CACHE_REFRESHED_AT

    try:
        payload = _dlm_json("/api/v1/dlm/lake-configuration/context")
        lakes = payload.get("data", {}).get("lakes", [])
        if not isinstance(lakes, list):
            lakes = []
        normalized = [_normalize_lake(item) for item in lakes if isinstance(item, dict)]
        with _CACHE_LOCK:
            _LAKE_CACHE = normalized
            _LAKE_CACHE_ERROR = None
            _LAKE_CACHE_REFRESHED_AT = time.time()
        return len(normalized), None
    except RuntimeError as exc:
        with _CACHE_LOCK:
            _LAKE_CACHE_ERROR = str(exc)
        return 0, str(exc)


def cached_lakes() -> tuple[list[dict[str, Any]], str | None, float | None]:
    with _CACHE_LOCK:
        return list(_LAKE_CACHE), _LAKE_CACHE_ERROR, _LAKE_CACHE_REFRESHED_AT


_load_dotenv()


class GenericLakesHandler(BaseHTTPRequestHandler):
    """Local MCP generic HTTP endpoint backed by cached DLM lake metadata.

    The Python adapter still calls inputs.invoke_tool(...). This helper exists
    only as a local runtime connector target. It prefetches lake context before
    the Assets/Core runtime call so local Core does not need to call back into
    itself while handling the MCP operation.
    """

    protocol_version = "HTTP/1.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/health":
            records, error, refreshed_at = cached_lakes()
            self.send_json({
                "status": "ok" if records else "warming",
                "record_count": len(records),
                "cache_ready": bool(records),
                "cache_error": error,
                "cache_refreshed_at": refreshed_at,
                "records": [],
            })
            return

        if parsed.path != "/lakes":
            self.send_json({"error": "not_found", "records": []}, status=404)
            return

        if (query.get("refresh") or [""])[0] in {"1", "true", "yes"}:
            count, error = refresh_lake_cache()
            if error is not None:
                self.send_json({"error": "dlm_proxy_refresh_failed", "message": error, "records": []}, status=502)
                return
            self.send_json({"records": [], "refreshed": True, "record_count": count})
            return

        try:
            records = self.fetch_lakes(query)
        except RuntimeError as exc:
            self.send_json({"error": "dlm_proxy_cache_unavailable", "message": str(exc), "records": []}, status=503)
            return

        self.send_json({"records": records})

    def fetch_lakes(self, query_params: dict[str, list[str]]) -> list[dict[str, Any]]:
        normalized, error, _ = cached_lakes()
        if not normalized:
            raise RuntimeError(error or "DLM lake cache is empty; refresh the proxy before runtime execution")

        text = (query_params.get("q") or [""])[0]
        query = self.query_text(text)
        if query:
            needle = query.lower()
            normalized = [
                lake for lake in normalized
                if needle in lake["lake_id"].lower()
                or needle in lake["name"].lower()
                or needle in lake["status"].lower()
            ]

        limit = self.limit(query_params, text)
        page = self.page(query_params, text)
        offset = (page - 1) * limit

        return normalized[offset: offset + limit]

    @staticmethod
    def query_text(text: str) -> str | None:
        normalized = text.strip()
        if not normalized:
            return None

        match = re.search(r"\bquery\s+([^;\n]+)", normalized, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            return value or None

        lower = normalized.lower()
        if "lake" in lower or "lakes" in lower:
            return None
        return normalized[:120]

    @staticmethod
    def limit(query_params: dict[str, list[str]], text: str) -> int:
        explicit = (query_params.get("limit") or [""])[0]
        if explicit.isdigit():
            return max(1, min(MAX_LIMIT, int(explicit)))

        match = re.search(r"\blimit\s+(\d+)\b", text, re.IGNORECASE)
        if not match:
            return DEFAULT_LIMIT
        return max(1, min(MAX_LIMIT, int(match.group(1))))

    @staticmethod
    def page(query_params: dict[str, list[str]], text: str) -> int:
        explicit = (query_params.get("page") or [""])[0]
        if explicit.isdigit():
            return max(1, min(100000, int(explicit)))

        match = re.search(r"\bpage\s+(\d+)\b", text, re.IGNORECASE)
        if match:
            return max(1, min(100000, int(match.group(1))))

        return 1

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def log_message(self, format: str, *args: Any) -> None:
        return


if __name__ == "__main__":
    port = int(os.getenv("ABSTRACT_MCP_DLM_PROXY_PORT", "8787"))
    count, error = refresh_lake_cache()
    status = f"prefetched {count} lake records" if error is None else f"prefetch failed: {error}"
    print(f"DLM lakes proxy running at http://127.0.0.1:{port}/lakes ({status})")
    server = ThreadingHTTPServer(("127.0.0.1", port), GenericLakesHandler)
    server.serve_forever()
