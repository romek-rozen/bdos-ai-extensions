"""
d4s_client.py — core DataForSEO REST client for BDOS (pure standard library).

No pip dependencies: auth, HTTP, retry and JSON handling all use urllib/base64/json.
The HTTP transport is injectable so the whole client is testable offline.

Every public method returns a dict with an ``ok`` key. On failure:
``{"ok": False, "error": "..."}`` — never raises for expected conditions (missing
credentials, API errors, HTTP errors, task timeouts).

Two call modes:
    * ``call(path, payload)``      — live endpoints, immediate result
    * task mode for endpoints without a ``live`` variant:
        - ``task(base_path, payload)``        blocking submit → poll → get
        - ``task_submit(base_path, payload)`` submit now, returns ``task_id``
        - ``task_fetch(base_path, task_id)``  collect one task later
        - ``tasks_ready(base_path)``          list tasks ready to collect
"""

import base64
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://api.dataforseo.com"
# Default locations searched for a .env file (package dir, then repo/cwd).
_DEFAULT_ENV_FILES = (
    str(pathlib.Path(__file__).resolve().parent / ".env"),
    str(pathlib.Path.cwd() / ".env"),
)
_OK_STATUS = 20000  # DataForSEO "Ok." status code (both envelope- and task-level)


class Client:
    def __init__(
        self,
        login=None,
        password=None,
        base_url=None,
        transport=None,
        env=None,
        env_file=None,
        sleeper=None,
        now=None,
        max_attempts=3,
        timeout=30.0,
        cache=True,
        cache_ttl=604800.0,
        cache_db=None,
    ):
        env = os.environ if env is None else env
        # Process env wins over a .env file; the file only fills in missing values.
        file_vars = _read_env_file(env_file if env_file is not None else _DEFAULT_ENV_FILES)
        env = {**file_vars, **env}
        self._login = login or env.get("DATAFORSEO_USERNAME") or env.get("DATAFORSEO_LOGIN")
        self._password = password or env.get("DATAFORSEO_PASSWORD")
        self._base_url = (base_url or env.get("DATAFORSEO_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self._transport = transport or _urllib_transport
        self._sleeper = sleeper or time.sleep
        self._now = now or time.monotonic
        self._max_attempts = max(1, int(max_attempts))
        self._http_timeout = timeout
        self._last_request = None
        # Response cache — avoids re-paying DataForSEO for an identical query.
        self._cache = bool(cache)
        self._cache_ttl = cache_ttl
        self._cache_db = cache_db

    # -- live -------------------------------------------------------------

    def call(self, path, payload=None, method="POST", no_cache=False):
        """Hit any live DataForSEO endpoint and return the parsed envelope.

        Successful responses are cached (keyed by path+payload) and reused within
        ``cache_ttl`` seconds, so repeating a query does not cost credits. Pass
        ``no_cache=True`` to force a fresh call and refresh the cache.
        """
        use_cache = self._cache and not no_cache
        if use_cache:
            from . import cache as _cache
            key = _cache.make_key(path, payload)
            hit = _cache.get(key, self._cache_ttl, db=self._cache_db)
            if hit is not None:
                return {**hit, "cached": True}
        r = self._request(method, path, payload)
        if use_cache and r.get("ok"):
            from . import cache as _cache
            _cache.put(_cache.make_key(path, payload), r, path=path, db=self._cache_db)
        return r

    # -- task mode --------------------------------------------------------

    def task_submit(self, base_path, payload):
        """POST to {base_path}/task_post without waiting; return the task id."""
        r = self._request("POST", base_path.rstrip("/") + "/task_post", payload)
        if not r["ok"]:
            return r
        tasks = r.get("tasks") or []
        task_id = tasks[0].get("id") if tasks else None
        return {"ok": True, "task_id": task_id, "cost": r.get("cost"), "raw": r.get("raw")}

    def task_fetch(self, base_path, task_id):
        """Collect a single task result: GET {base_path}/task_get/advanced/{id}."""
        return self._request("GET", base_path.rstrip("/") + "/task_get/advanced/" + str(task_id))

    def tasks_ready(self, base_path):
        """List tasks ready to collect: GET {base_path}/tasks_ready."""
        return self._request("GET", base_path.rstrip("/") + "/tasks_ready")

    def task(self, base_path, payload, timeout=120.0, interval=5.0):
        """Blocking convenience: submit, then poll task_get until ready or timeout."""
        sub = self.task_submit(base_path, payload)
        if not sub["ok"]:
            return sub
        task_id = sub["task_id"]
        start = self._now()
        while True:
            got = self.task_fetch(base_path, task_id)
            if got["ok"] and _task_ready(got):
                return got
            if self._now() - start >= timeout:
                return {"ok": False, "error": "task timeout", "task_id": task_id}
            self._sleeper(interval)

    # -- internals --------------------------------------------------------

    def _request(self, method, path, payload=None):
        if not self._login or not self._password:
            return {"ok": False, "error": "missing DataForSEO credentials "
                    "(set DATAFORSEO_USERNAME/DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD)"}

        url = self._base_url + path
        token = base64.b64encode(f"{self._login}:{self._password}".encode()).decode()
        headers = {"Authorization": "Basic " + token, "Content-Type": "application/json"}
        body = json.dumps(payload).encode("utf-8") if payload is not None else None

        status, raw_bytes = self._send_with_retry(method, url, headers, body)
        if status is None:
            return {"ok": False, "error": raw_bytes}  # transport error message
        if status < 200 or status >= 300:
            return {"ok": False, "error": f"HTTP {status}",
                    "status": status, "raw": _safe_text(raw_bytes)}

        try:
            envelope = json.loads(raw_bytes.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            return {"ok": False, "error": f"invalid JSON response: {exc}"}

        if envelope.get("status_code") != _OK_STATUS:
            return {"ok": False,
                    "error": envelope.get("status_message", "API error"),
                    "status_code": envelope.get("status_code"), "raw": envelope}

        tasks = envelope.get("tasks") or []
        result = []
        for t in tasks:
            r = t.get("result")
            if r:
                result.extend(r)
        return {"ok": True, "cost": envelope.get("cost"),
                "tasks": tasks, "result": result, "raw": envelope}

    def _send_with_retry(self, method, url, headers, body):
        last = (None, "request failed")
        for attempt in range(self._max_attempts):
            status, raw = self._transport(method, url, headers, body)
            self._last_request = {"method": method, "url": url, "headers": headers, "body": body}
            if status == 429 or (status is not None and status >= 500):
                last = (status, raw)
                if attempt < self._max_attempts - 1:
                    self._sleeper(0.5 * (2 ** attempt))
                    continue
            return status, raw
        return last


def _read_env_file(paths):
    """Parse the first existing .env file into a dict (KEY=VALUE lines).

    ``paths`` may be a single path or an iterable of candidates; the first that
    exists is used. Blank lines and ``#`` comments are ignored; surrounding
    quotes and an optional ``export`` prefix are stripped. Never raises.
    """
    if isinstance(paths, str):
        paths = (paths,)
    for path in paths:
        try:
            text = pathlib.Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                out[key] = value
        return out
    return {}


def creds_status(env_file=None):
    """Report whether DataForSEO credentials are configured, with next steps.

    Lets a BDOS agent check readiness before calling and guide a non-technical
    user. Returns {"ok", "ready", "has_login", "has_password", "env_path",
    "message"}. Reads the same sources as ``Client`` (process env + .env file).
    """
    c = Client(env_file=env_file)
    ready = bool(c._login and c._password)
    env_path = str(pathlib.Path(__file__).resolve().parent / ".env")
    if ready:
        message = f"DataForSEO ready (user: {c._login})."
    else:
        missing = []
        if not c._login:
            missing.append("DATAFORSEO_USERNAME")
        if not c._password:
            missing.append("DATAFORSEO_PASSWORD")
        message = (
            f"DataForSEO not configured (missing: {', '.join(missing)}).\n"
            f"  Edit {env_path} and set:\n"
            "    DATAFORSEO_USERNAME=you@example.com\n"
            "    DATAFORSEO_PASSWORD=your-api-password\n"
            "  Get an account: https://skq.pl/data4seo   (.env is gitignored)"
        )
    return {
        "ok": True,
        "ready": ready,
        "has_login": bool(c._login),
        "has_password": bool(c._password),
        "env_path": env_path,
        "message": message,
    }


def _task_ready(got):
    tasks = got.get("tasks") or []
    if not tasks:
        return False
    return tasks[0].get("status_code") == _OK_STATUS


def _safe_text(raw_bytes):
    try:
        return raw_bytes.decode("utf-8", "replace")
    except Exception:
        return str(raw_bytes)


def _urllib_transport(method, url, headers, body, timeout=30.0):
    """Default HTTP transport. Returns (status_code, response_bytes).

    Network/URL errors return (None, message) so the client can surface them as
    ``{"ok": False, "error": ...}`` rather than raising.
    """
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError) as exc:
        return None, f"transport error: {exc}"
