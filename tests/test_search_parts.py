"""The parts of Phase 1B that work without a database or Ollama: settings, vector text, rank fusion."""

import tempfile
import unittest
from pathlib import Path

from labour_rag.config import load_settings
from labour_rag.db import vector_literal
from labour_rag.search import rrf_fuse


def results(*ids):
    return [{"id": i, "rank": n, "score": 0.0} for n, i in enumerate(ids, 1)]


class Fusion(unittest.TestCase):
    def test_chunk_in_both_lists_wins(self):
        fused = rrf_fuse({"semantic": results("a", "b", "c"), "keyword": results("c", "d")}, k=4)
        self.assertEqual([r["id"] for r in fused], ["c", "a", "b", "d"])    # c: 1/63 + 1/61 beats a: 1/61
        self.assertEqual((fused[0]["semantic_rank"], fused[0]["keyword_rank"]), (3, 1))
        self.assertEqual((fused[1]["semantic_rank"], fused[1]["keyword_rank"]), (1, None))
        self.assertEqual([r["rank"] for r in fused], [1, 2, 3, 4])

    def test_scores_and_cut(self):
        fused = rrf_fuse({"semantic": results("a"), "keyword": results("a", "b")}, k=1)
        self.assertEqual(len(fused), 1)
        self.assertAlmostEqual(fused[0]["score"], 2 / 61)


class Settings(unittest.TestCase):
    def test_env_file_is_read(self):
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / ".env"
            env.write_text("# comment\nPOSTGRES_DB=x\nPOSTGRES_USER=u\nPOSTGRES_PASSWORD='p w'\nEMBED_MODEL=other\n")
            s = load_settings(env)
        self.assertEqual((s.postgres_db, s.postgres_password, s.embed_model, s.postgres_port), ("x", "p w", "other", 5433))

    def test_vector_literal(self):
        self.assertEqual(vector_literal([0.5, -1.0, 1e-8]), "[0.5,-1,1e-08]")


if __name__ == "__main__":
    unittest.main()
