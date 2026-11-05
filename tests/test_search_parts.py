"""The parts of Phase 1B and 3A that work without a database or Ollama: settings, vector text, ways of fusing."""

import tempfile
import unittest
from pathlib import Path

from labour_rag.config import load_settings
from labour_rag.db import vector_literal
from labour_rag.search import fuse, reserved_places, rrf_fuse


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

    def test_equal_weights_let_the_bottom_of_both_lists_beat_the_top_of_one(self):
        semantic = results("a", *[f"s{i}" for i in range(48)], "b")
        keyword = results(*[f"k{i}" for i in range(49)], "b")
        self.assertEqual(rrf_fuse({"semantic": semantic, "keyword": keyword}, k=1)[0]["id"], "b")
        weighted = rrf_fuse({"semantic": semantic, "keyword": keyword}, k=1, weights={"semantic": 2})
        self.assertEqual(weighted[0]["id"], "a")

    def test_reserved_places(self):
        semantic, keyword = results("a", "b", "c", "d"), results("b", "x", "y", "z")
        ordered = reserved_places(semantic, keyword, first=2, added=2)
        self.assertEqual([r["id"] for r in ordered], ["a", "b", "x", "y", "c", "d"])    # keyword's "b" is already in

    def test_reserved_places_doesnt_repeat_a_chunk_further_down(self):
        ordered = reserved_places(results("a", "b", "c"), results("c"), first=1, added=1)
        self.assertEqual([r["id"] for r in ordered], ["a", "c", "b"])

    def test_semantic_keeps_its_order_and_knows_the_keyword_rank(self):
        fused = fuse("semantic", results("a", "b"), results("x", "b"), "μια ερώτηση", k=5)
        self.assertEqual([r["id"] for r in fused], ["a", "b"])
        self.assertEqual((fused[1]["rank"], fused[1]["semantic_rank"], fused[1]["keyword_rank"]), (2, 2, 2))

    def test_law_lookup_uses_keyword_only_when_a_law_is_named(self):
        semantic = results(*"abcdefgh")
        keyword = results("x", "y")
        plain = fuse("law-lookup", semantic, keyword, "Πόσες μέρες άδεια έχω;", k=8)
        self.assertEqual([r["id"] for r in plain], list("abcdefgh"))
        named = fuse("law-lookup", semantic, keyword, "Τι λέει το άρθρο 2 του Ν. 1837/1989;", k=8)
        self.assertEqual([r["id"] for r in named], list("abcdefxy"))
        self.assertEqual(named[6]["keyword_rank"], 1)

    def test_unknown_fusion(self):
        with self.assertRaises(ValueError):
            fuse("nonsense", [], [], "ερώτηση")


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
