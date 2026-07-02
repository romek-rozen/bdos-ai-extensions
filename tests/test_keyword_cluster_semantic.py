"""Semantic embedding provider tests (mock HTTP, no network)."""
import json
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from keyword_cluster import embed as embed_mod  # noqa: E402


class TestEmbedOpenAI(unittest.TestCase):
    def test_openai_shape(self):
        fake = json.dumps({"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}).encode()
        prev = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["OPENAI_API_KEY"] = "sk-x"
            with mock.patch.object(embed_mod, "_http_post_json", return_value=json.loads(fake)):
                vecs = embed_mod.embed(["a", "b"], provider="openai", model="text-embedding-3-small")
            self.assertEqual(vecs, [[0.1, 0.2], [0.3, 0.4]])
        finally:
            if prev is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = prev


class TestEmbedOllama(unittest.TestCase):
    def test_ollama_shape(self):
        fake = {"embeddings": [[1.0, 2.0], [3.0, 4.0]]}
        with mock.patch.object(embed_mod, "_http_post_json", return_value=fake) as post:
            vecs = embed_mod.embed(["a", "b"], provider="ollama", model="nomic-embed-text")
        self.assertEqual(vecs, [[1.0, 2.0], [3.0, 4.0]])
        url = post.call_args[0][0]
        self.assertTrue(url.endswith("/api/embed"))


class TestEmbedBatching(unittest.TestCase):
    def test_batches_and_flattens(self):
        def fake_post(url, payload, headers, timeout=120):
            return {"data": [{"embedding": [float(len(t))]} for t in payload["input"]]}

        prev = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["OPENAI_API_KEY"] = "sk-x"
            with mock.patch.object(embed_mod, "_http_post_json", side_effect=fake_post) as post:
                texts = ["a", "bb", "ccc", "dddd", "eeeee"]
                vecs = embed_mod.embed(texts, provider="openai", batch_size=2)
            self.assertEqual(post.call_count, 3)
            self.assertEqual(vecs, [[1.0], [2.0], [3.0], [4.0], [5.0]])
        finally:
            if prev is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = prev


class TestEmbedMissingKey(unittest.TestCase):
    def test_missing_key_raises(self):
        prev = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ.pop("OPENAI_API_KEY", None)
            with mock.patch.object(embed_mod, "_http_post_json", return_value={"data": []}):
                with self.assertRaises(RuntimeError):
                    embed_mod.embed(["a"], provider="openai")
        finally:
            if prev is not None:
                os.environ["OPENAI_API_KEY"] = prev


try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


@unittest.skipUnless(HAVE_NUMPY, "numpy required (heavy venv)")
class TestWhiten(unittest.TestCase):
    def test_whiten_decorrelates(self):
        from keyword_cluster.whiten import whiten_batch
        rng = np.random.default_rng(0)
        base = rng.normal(size=(200, 8))
        X = base @ rng.normal(size=(8, 32))  # correlated, anisotropic
        W = whiten_batch(X, reduce_dim=8)
        # rows are finite, L2-normalized
        norms = np.linalg.norm(W, axis=1)
        self.assertTrue(np.allclose(norms, 1.0, atol=1e-6))
        self.assertTrue(np.isfinite(W).all())

    def test_whiten_single_row_no_warning(self):
        import warnings

        from keyword_cluster.whiten import whiten_batch
        rng = np.random.default_rng(1)
        X = rng.normal(size=(1, 32))
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            W = whiten_batch(X)
        self.assertEqual(W.shape, (1, 32))
        self.assertTrue(np.isfinite(W).all())
        self.assertTrue(np.allclose(np.linalg.norm(W, axis=1), 1.0, atol=1e-6))

    def test_whiten_rank_deficient(self):
        from keyword_cluster.whiten import whiten_batch
        rng = np.random.default_rng(2)
        X = rng.normal(size=(3, 32))  # n < d: rank-deficient batch
        W = whiten_batch(X)
        self.assertEqual(W.shape[0], 3)
        self.assertTrue(np.isfinite(W).all())
        self.assertTrue(np.allclose(np.linalg.norm(W, axis=1), 1.0, atol=1e-6))


if __name__ == "__main__":
    unittest.main()
