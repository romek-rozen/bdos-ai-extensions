"""
Unit tests for d4s — DataForSEO REST client for BDOS.

Fully offline: a fake transport is injected into the client, so no network is
touched. Covers auth/env handling, the live `call()` envelope, retry on 429/5xx,
and the task-mode primitives (submit / fetch / tasks_ready / blocking task()).
"""

import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from d4s import Client  # noqa: E402


def _body(obj):
    return json.dumps(obj).encode("utf-8")


def _envelope(result, status_code=20000, cost=0.01, task_status=20000, task_id="t-1"):
    return {
        "status_code": status_code,
        "status_message": "Ok." if status_code == 20000 else "Error.",
        "cost": cost,
        "tasks": [
            {
                "id": task_id,
                "status_code": task_status,
                "status_message": "Ok." if task_status == 20000 else "In queue.",
                "result": result,
            }
        ],
    }


class FakeTransport:
    """Records requests; returns queued (status, bytes) responses in order.

    A queued response may be a plain (status, bytes) tuple, or a callable taking
    (method, url, headers, body) and returning that tuple.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def __call__(self, method, url, headers, body):
        self.requests.append({"method": method, "url": url, "headers": headers, "body": body})
        resp = self._responses.pop(0)
        if callable(resp):
            resp = resp(method, url, headers, body)
        return resp


def _client(responses, **kw):
    kw.setdefault("login", "user@example.com")
    kw.setdefault("password", "secret")
    kw.setdefault("sleeper", lambda _s: None)  # no real sleeping
    return Client(transport=FakeTransport(responses), **kw)


class TestAuthAndEnv(unittest.TestCase):
    def test_missing_credentials_returns_error(self):
        c = Client(login=None, password=None, transport=FakeTransport([]))
        r = c.call("/v3/whatever/live", [{}])
        self.assertFalse(r["ok"])
        self.assertIn("credential", r["error"].lower())

    def test_reads_credentials_from_env(self):
        c = Client(env={"DATAFORSEO_USERNAME": "u", "DATAFORSEO_PASSWORD": "p"},
                   transport=FakeTransport([(200, _body(_envelope([{"x": 1}])))]),
                   sleeper=lambda _s: None)
        r = c.call("/v3/x/live", [{}])
        self.assertTrue(r["ok"])
        # Basic auth header built from env creds
        auth = c._last_request["headers"]["Authorization"]
        self.assertTrue(auth.startswith("Basic "))

    def test_login_alias_env(self):
        c = Client(env={"DATAFORSEO_LOGIN": "u", "DATAFORSEO_PASSWORD": "p"},
                   transport=FakeTransport([(200, _body(_envelope([{"x": 1}])))]),
                   sleeper=lambda _s: None)
        r = c.call("/v3/x/live", [{}])
        self.assertTrue(r["ok"])


class TestCall(unittest.TestCase):
    def test_success_envelope_flattening(self):
        c = _client([(200, _body(_envelope([{"keyword": "buty", "search_volume": 1000}])))])
        r = c.call("/v3/keywords_data/google_ads/search_volume/live", [{"keywords": ["buty"]}])
        self.assertTrue(r["ok"])
        self.assertEqual(r["cost"], 0.01)
        self.assertEqual(r["result"][0]["keyword"], "buty")
        self.assertIn("raw", r)

    def test_posts_payload_as_json_to_correct_url(self):
        c = _client([(200, _body(_envelope([{}])))])
        c.call("/v3/x/live", [{"keywords": ["a"]}])
        req = c._last_request
        self.assertEqual(req["method"], "POST")
        self.assertTrue(req["url"].endswith("/v3/x/live"))
        self.assertEqual(json.loads(req["body"].decode()), [{"keywords": ["a"]}])

    def test_api_level_error_is_not_ok(self):
        c = _client([(200, _body(_envelope([], status_code=40400)))])
        r = c.call("/v3/x/live", [{}])
        self.assertFalse(r["ok"])
        self.assertIn("raw", r)

    def test_http_error_status_is_not_ok(self):
        c = _client([(500, b"boom"), (500, b"boom"), (500, b"boom")])
        r = c.call("/v3/x/live", [{}])
        self.assertFalse(r["ok"])


class TestRetry(unittest.TestCase):
    def test_retries_on_429_then_succeeds(self):
        c = _client([(429, b"slow down"),
                     (200, _body(_envelope([{"ok": 1}])))],
                    max_attempts=3)
        r = c.call("/v3/x/live", [{}])
        self.assertTrue(r["ok"])
        self.assertEqual(len(c._transport.requests), 2)

    def test_gives_up_after_max_attempts(self):
        c = _client([(503, b"a"), (503, b"b"), (503, b"c")], max_attempts=3)
        r = c.call("/v3/x/live", [{}])
        self.assertFalse(r["ok"])
        self.assertEqual(len(c._transport.requests), 3)


class TestTaskMode(unittest.TestCase):
    BASE = "/v3/serp/google/ads_search"

    def test_task_submit_returns_task_id(self):
        c = _client([(200, _body(_envelope([{"task_id": "t-42"}], task_id="t-42")))])
        r = c.task_submit(self.BASE, [{"advertiser_id": "AR1"}])
        self.assertTrue(r["ok"])
        self.assertEqual(r["task_id"], "t-42")
        self.assertTrue(c._last_request["url"].endswith(self.BASE + "/task_post"))

    def test_task_fetch_gets_by_id(self):
        c = _client([(200, _body(_envelope([{"items": ["ad1"]}])))])
        r = c.task_fetch(self.BASE, "t-42")
        self.assertTrue(r["ok"])
        self.assertEqual(r["result"][0]["items"], ["ad1"])
        self.assertEqual(c._last_request["method"], "GET")
        self.assertTrue(c._last_request["url"].endswith(self.BASE + "/task_get/advanced/t-42"))

    def test_tasks_ready_lists_ids(self):
        c = _client([(200, _body(_envelope([{"id": "t-1"}, {"id": "t-2"}])))])
        r = c.tasks_ready(self.BASE)
        self.assertTrue(r["ok"])
        self.assertEqual([x["id"] for x in r["result"]], ["t-1", "t-2"])
        self.assertTrue(c._last_request["url"].endswith(self.BASE + "/tasks_ready"))

    def test_task_blocking_polls_until_ready(self):
        # 1) task_post -> id, 2) task_get in-queue, 3) task_get ready
        c = _client([
            (200, _body(_envelope([{"task_id": "t-9"}], task_id="t-9"))),
            (200, _body(_envelope(None, task_status=40602))),   # in queue
            (200, _body(_envelope([{"items": ["adX"]}]))),      # ready
        ])
        r = c.task(self.BASE, [{"advertiser_id": "AR1"}], timeout=10, interval=0)
        self.assertTrue(r["ok"])
        self.assertEqual(r["result"][0]["items"], ["adX"])

    def test_task_blocking_times_out(self):
        # Clock jumps past the 10s timeout after the first poll; clamps so extra
        # now() calls never raise.
        ticks = [0.0, 0.0, 99.0]
        clock = {"i": 0}

        def now():
            i = min(clock["i"], len(ticks) - 1)
            clock["i"] += 1
            return ticks[i]

        c = _client([
            (200, _body(_envelope([{"task_id": "t-9"}], task_id="t-9"))),
            (200, _body(_envelope(None, task_status=40602))),
            (200, _body(_envelope(None, task_status=40602))),
        ], now=now)
        r = c.task(self.BASE, [{"advertiser_id": "AR1"}], timeout=10, interval=0)
        self.assertFalse(r["ok"])
        self.assertIn("timeout", r["error"].lower())
        self.assertEqual(r["task_id"], "t-9")


if __name__ == "__main__":
    unittest.main()
