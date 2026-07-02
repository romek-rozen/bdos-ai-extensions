"""
Unit tests for the throttled update check — pure logic, no network/git.
"""

import pathlib
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import updates  # noqa: E402


def _fake_run(stdout):
    """Build a fake subprocess.CompletedProcess-like object."""
    return types.SimpleNamespace(stdout=stdout, stderr="", returncode=0)


class TestUpdates(unittest.TestCase):
    def setUp(self):
        # Isolate the cache file per test.
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_cache = updates._CACHE
        updates._CACHE = pathlib.Path(self._tmp.name) / ".update_check.json"
        self._orig_run = updates._run

    def tearDown(self):
        updates._CACHE = self._orig_cache
        updates._run = self._orig_run
        self._tmp.cleanup()

    def test_parses_behind_from_rev_list(self):
        def fake(args, timeout=15):
            if args[0] == "rev-parse":
                return _fake_run("main\n")
            if args[0] == "rev-list":
                return _fake_run("3\n")
            return _fake_run("")
        updates._run = fake
        r = updates.check_update(force=True, now=1000.0)
        self.assertTrue(r["ok"])
        self.assertEqual(r["behind"], 3)
        self.assertFalse(r["cached"])

    def test_throttle_returns_cache_without_fetch(self):
        calls = {"n": 0}

        def fake(args, timeout=15):
            calls["n"] += 1
            if args[0] == "rev-parse":
                return _fake_run("main\n")
            if args[0] == "rev-list":
                return _fake_run("2\n")
            return _fake_run("")
        updates._run = fake
        first = updates.check_update(force=True, now=1000.0)
        self.assertEqual(first["behind"], 2)
        after_first = calls["n"]

        # Second call within TTL: no git activity, served from cache.
        second = updates.check_update(force=False, now=1000.0 + 600)
        self.assertTrue(second["cached"])
        self.assertEqual(second["behind"], 2)
        self.assertEqual(calls["n"], after_first)

    def test_graceful_on_exception(self):
        def boom(args, timeout=15):
            raise RuntimeError("git exploded")
        updates._run = boom
        r = updates.check_update(force=True, now=1000.0)
        self.assertTrue(r["ok"])
        self.assertEqual(r["behind"], 0)

    def test_read_version(self):
        self.assertEqual(updates.read_version(), updates.read_version())
        self.assertTrue(updates.read_version())  # non-empty string


if __name__ == "__main__":
    unittest.main()
