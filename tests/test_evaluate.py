"""Phase 2 parts that run without a database or model: matching key facts and scoring."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from labour_rag.evaluate import (FROZEN_TAG, HAIKU_TAG, TEST_SETTINGS, claim_test_run, config_name, dev_run_finished, first_rank, frozen_changes, frozen_refusal, gold_documents,
                                 problem, score_answer, score_retrieval, summarise_group, test_run_refusal)
from labour_rag.key_facts import fact_present, stem
from scripts.check_eval_set import copied_run, quote_in
from scripts.retrieval_report import chance_of_split, pick_winner

NOTE = "Σημείωση: Οι πηγές φτάνουν μέχρι το 1999."


class WordForms(unittest.TestCase):
    def test_endings_are_ignored(self):
        for a, b in (("αποδοχες", "αποδοχων"), ("απολυση", "απολυσης"), ("μηνες", "μηνων"), ("εβδομαδες", "εβδομαδα"),
                     ("εργοδοτης", "εργοδοτη")):
            self.assertEqual(stem(a), stem(b))

    def test_salary_is_not_half(self):
        self.assertNotEqual(stem("μισθος"), stem("μισος"))


class Facts(unittest.TestCase):
    def test_accents_case_and_word_forms(self):
        self.assertTrue(fact_present("Αποδοχές αυξημένες κατά 100%", "ΟΙ ΑΠΟΔΟΧΩΝ ΑΥΞΗΜΕΝΩΝ κατα 100 %"))

    def test_a_number_may_be_a_word_or_digits_or_part_of_a_word(self):
        self.assertTrue(fact_present("Τρεις μήνες πριν από την απόλυση", "3 μήνες πριν την απόλυση [1]"))
        self.assertTrue(fact_present("3 μήνες πριν από την απόλυση", "τριών μηνών πριν από την απόλυση"))
        self.assertTrue(fact_present("Το πολύ μέσα σε δύο μήνες από την αίτηση", "εντός διμήνου από την αίτηση"))
        self.assertTrue(fact_present("Πέντε χρόνια", "πενταετή χρόνια"))

    def test_every_number_must_be_there(self):
        self.assertFalse(fact_present("50% από 60 έως 120 ώρες", "50% από 60 ώρες τον χρόνο"))
        self.assertFalse(fact_present("16 εβδομάδες συνολικά", "14 εβδομάδες συνολικά"))

    def test_citation_markers_are_not_numbers(self):
        self.assertFalse(fact_present("2 ώρες την ημέρα", "ώρες την ημέρα [2]"))

    def test_times_on_a_twelve_hour_clock(self):
        self.assertTrue(fact_present("Απαγορεύεται η εργασία μεταξύ 21:30 και 06:00",
                                     "απαγορεύεται η εργασία μεταξύ 09.30 εσπερινής και 06.00 πρωινής"))
        self.assertTrue(fact_present("Λήγει στις 06:00", "λήγει στις 6 το πρωί"))

    def test_two_digit_year_of_a_law(self):
        self.assertTrue(fact_present("Αφορά όσους υπάγονται στον Ν. 1648/86", "όσοι υπάγονται στον Ν. 1648/1986"))

    def test_half_in_old_and_new_words(self):
        self.assertTrue(fact_present("Το μισό της αποζημίωσης", "το ήμισυ της αποζημιώσεως"))

    def test_half_is_required_like_a_number(self):
        # Real model output: it gave the ceiling of one salary for the Easter bonus, which is half a salary.
        self.assertFalse(fact_present("Μισός μηνιαίος μισθός για όσους παίρνουν μισθό",
                                      "δεν μπορεί να ξεπεράσει έναν μηνιαίο μισθό για όσους παίρνουν μισθό"))

    def test_with_a_number_half_of_the_other_words_is_enough(self):
        self.assertTrue(fact_present("Προϋπόθεση 12 μήνες συνεχούς απασχόλησης", "μετά από 12 μήνες απασχόληση"))

    def test_too_few_of_the_words_is_not_enough(self):
        self.assertFalse(fact_present("Η ασθένεια πρέπει να αποδεικνύεται", "η σύμβαση λύεται"))


ITEM = {"id": "x", "answerable": True, "key_facts": ["Τρεις μήνες", "Έγγραφη καταγγελία"],
        "gold_sources": [{"chunk_ids": ["glc-41850-005"]}]}
FUSED = [{"id": "glc-00001-000", "rank": 1, "semantic_rank": 1, "keyword_rank": None},
         {"id": "glc-41850-005", "rank": 2, "semantic_rank": None, "keyword_rank": 7}]
KEPT = [{"n": 1, "id": "glc-00001-000", "doc_id": 1}, {"n": 2, "id": "glc-41850-005", "doc_id": 41850}]
LISTS = {"semantic": [{"id": "glc-41850-005", "rank": 4}], "keyword": [{"id": "glc-00001-000", "rank": 1}]}


class TestGuard(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.results = Path(folder.name)
        self.claims = self.results / "test_runs.json"

    def claim(self, system, run):
        return claim_test_run(system, run, self.claims, self.results)

    def finish(self, run):
        (self.results / run).mkdir()
        (self.results / run / "summary.json").write_text("{}", encoding="utf-8")

    def test_the_first_run_of_a_system_is_recorded(self):
        self.assertEqual(self.claim("one-shot", "2026-11-04_a-test"), "2026-11-04_a-test")
        self.assertEqual(json.loads(self.claims.read_text(encoding="utf-8")),
                         {"one-shot": {"run": "2026-11-04_a-test", "started": "2026-11-04"}})

    def test_a_system_gets_one_run_and_another_system_gets_its_own(self):
        self.claim("one-shot", "2026-11-04_a-test")
        self.finish("2026-11-04_a-test")
        with self.assertRaises(SystemExit):
            self.claim("one-shot", "2026-11-05_a-test")
        with self.assertRaises(SystemExit):
            self.claim("one-shot", "2026-11-05_other-settings-test")
        self.assertEqual(self.claim("agent", "2026-11-06_agent-test"), "2026-11-06_agent-test")
        self.assertEqual(set(json.loads(self.claims.read_text(encoding="utf-8"))), {"one-shot", "agent"})

    def test_an_interrupted_run_continues_but_cant_change_its_settings(self):
        self.claim("one-shot", "2026-11-04_a-test")
        self.assertEqual(self.claim("one-shot", "2026-11-05_a-test"), "2026-11-04_a-test")
        with self.assertRaises(SystemExit):
            self.claim("one-shot", "2026-11-05_other-settings-test")


class WhoMayUseTheTestSplit(unittest.TestCase):
    def test_only_these_systems_are_allowed_a_run(self):
        self.assertEqual(set(TEST_SETTINGS), {"oneshot-v2", "agent", "oneshot-haiku", "agent-haiku"})
        self.assertIn("no test run left", test_run_refusal("one-shot", TEST_SETTINGS["oneshot-v2"]))

    def test_each_runs_with_its_own_settings(self):
        for system, settings in TEST_SETTINGS.items():
            self.assertIsNone(test_run_refusal(system, {**settings, "split": "test", "pool": 30}))

    def test_other_settings_are_refused(self):
        v2 = TEST_SETTINGS["oneshot-v2"]
        for change in ({"fusion": "rrf"}, {"max_per_document": 4}, {"embedding": "bge-m3"}, {"number_rule": "digits"}, {"enhancer": "variants"}):
            self.assertIn(next(iter(change)), test_run_refusal("oneshot-v2", {**v2, **change}))
        self.assertIn("max_per_document", test_run_refusal("agent", {**TEST_SETTINGS["agent"], "max_per_document": 2}))

    def test_a_haiku_system_has_the_same_settings_as_its_local_one(self):
        self.assertEqual(TEST_SETTINGS["oneshot-haiku"], TEST_SETTINGS["oneshot-v2"])
        self.assertEqual(TEST_SETTINGS["agent-haiku"], TEST_SETTINGS["agent"])


class FrozenCode(unittest.TestCase):
    """In a small git repository of its own, so that these tests don't depend on the state of this one."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        (self.root / "labour_rag").mkdir()
        self.judge, self.evaluate = self.root / "labour_rag/judge.py", self.root / "labour_rag/evaluate.py"
        self.judge.write_text("a\n", encoding="utf-8")
        self.evaluate.write_text("a\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "x")

    def git(self, *arguments):
        subprocess.run(["git", *arguments], cwd=self.root, check=True, capture_output=True)

    def test_without_the_tag_it_counts_as_changed(self):
        self.assertTrue(frozen_changes(self.root))

    def test_a_change_to_the_frozen_code_shows(self):
        self.git("tag", FROZEN_TAG)
        self.assertEqual(frozen_changes(self.root), "")
        self.judge.write_text("b\n", encoding="utf-8")
        self.assertIn("judge.py", frozen_changes(self.root))

    def test_evaluate_stays_open(self):
        self.git("tag", FROZEN_TAG)
        self.evaluate.write_text("b\n", encoding="utf-8")
        self.assertEqual(frozen_changes(self.root), "")

    def test_a_new_file_next_to_the_frozen_code_is_no_change(self):
        self.git("tag", FROZEN_TAG)
        (self.root / "labour_rag/haiku_client.py").write_text("x\n", encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "y")
        self.assertEqual(frozen_changes(self.root), "")

    def test_a_deleted_frozen_file_shows(self):
        self.git("tag", FROZEN_TAG)
        self.judge.unlink()
        self.assertIn("judge.py", frozen_changes(self.root))

    def test_a_haiku_system_needs_both_tags(self):
        self.git("tag", FROZEN_TAG)
        self.assertIsNone(frozen_refusal("agent", self.root))
        self.assertIn(HAIKU_TAG, frozen_refusal("agent-haiku", self.root))
        self.git("tag", HAIKU_TAG)
        self.assertIsNone(frozen_refusal("agent-haiku", self.root))
        self.judge.write_text("b\n", encoding="utf-8")
        self.assertIn(FROZEN_TAG, frozen_refusal("agent-haiku", self.root))


class DevBeforeTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.results = Path(folder.name)
        self.config = {"system": "agent-haiku", "split": "test", "retrieval_only": False, **TEST_SETTINGS["agent-haiku"]}
        self.dev_run = self.results / "2026-11-06_agent-haiku-qwen3-4b-semantic-units-limit4-dev"

    def test_a_test_run_needs_a_finished_dev_run(self):
        self.assertFalse(dev_run_finished(self.config, self.results))
        self.dev_run.mkdir()
        self.assertFalse(dev_run_finished(self.config, self.results), "started isn't finished")
        (self.dev_run / "summary.json").write_text("{}", encoding="utf-8")
        self.assertTrue(dev_run_finished(self.config, self.results))

    def test_the_other_systems_dev_run_doesnt_count(self):
        self.dev_run.mkdir()
        (self.dev_run / "summary.json").write_text("{}", encoding="utf-8")
        self.assertFalse(dev_run_finished({**self.config, "system": "oneshot-haiku", **TEST_SETTINGS["oneshot-haiku"]}, self.results))


class Winner(unittest.TestCase):
    def counts(self, **others):
        return {"semantic": 10, "rrf": 10, "weighted": 10, "reserved": 10, "law-lookup": 10, **others}

    def test_a_clear_win(self):
        self.assertEqual(pick_winner(self.counts(rrf=13, semantic=11)), "rrf")

    def test_within_one_question_the_simpler_one_wins(self):
        self.assertEqual(pick_winner(self.counts(reserved=11)), "semantic")
        self.assertEqual(pick_winner(self.counts(semantic=8, rrf=9, reserved=10, weighted=7, **{"law-lookup": 7})), "rrf")

    def test_chance_of_a_split(self):
        self.assertAlmostEqual(chance_of_split(6, 1), 16 / 128)
        self.assertEqual(chance_of_split(1, 1), 1.0)


class RunNames(unittest.TestCase):
    def test_fusion_is_in_the_name(self):
        config = {"retrieval_only": True, "embedding": "qwen3-4b", "fusion": "semantic", "max_per_document": 2, "split": "dev"}
        self.assertEqual(config_name(config), "retrieval-qwen3-4b-semantic-limit2-dev")
        config = {**config, "retrieval_only": False, "embedding": "bge-m3", "fusion": "rrf", "split": "test"}
        self.assertEqual(config_name(config), "oneshot-rrf-limit2-test")


class Scores(unittest.TestCase):
    def test_gold_document_comes_from_the_chunk_id(self):
        self.assertEqual(gold_documents(ITEM), {41850})

    def test_rank_in_a_list(self):
        self.assertEqual(first_rank(FUSED, {"glc-41850-005"}), 2)
        self.assertEqual(first_rank(FUSED, {"glc-41850-005"}, "keyword_rank"), 7)
        self.assertIsNone(first_rank(FUSED, {"glc-99999-000"}))

    def test_retrieval(self):
        score = score_retrieval(ITEM, FUSED, KEPT, LISTS)
        self.assertEqual((score["rank"], score["reciprocal_rank"], score["in_context"]), (2, 0.5, True))
        missed = score_retrieval(ITEM, FUSED[:1], KEPT[:1], LISTS)
        self.assertEqual((missed["rank"], missed["reciprocal_rank"], missed["in_context"]), (None, 0.0, False))

    def test_ranks_in_each_list_come_from_the_lists_not_the_final_order(self):
        score = score_retrieval(ITEM, FUSED[:1], KEPT[:1], LISTS)
        self.assertEqual((score["semantic_rank"], score["keyword_rank"]), (4, None))

    def test_why_a_gold_chunk_was_removed(self):
        removed = [{"id": "glc-00001-000", "reason": "near-duplicate"}, {"id": "glc-41850-005", "reason": "same document"}]
        self.assertEqual(score_retrieval(ITEM, FUSED, KEPT[:1], LISTS, removed)["removed_as"], "same document")
        self.assertIsNone(score_retrieval(ITEM, FUSED, KEPT, LISTS)["removed_as"])

    def test_no_gold_chunks_means_no_retrieval_score(self):
        self.assertIsNone(score_retrieval({"gold_sources": []}, FUSED, KEPT, LISTS))

    def test_answer(self):
        check = {"citations": [2], "ok": True, "refusal": False}
        answer = f"Τρεις μήνες νωρίτερα [2].\n\n{NOTE}"
        score = score_answer(ITEM, answer, KEPT, check, NOTE)
        self.assertEqual(score["fact_share"], 0.5)
        self.assertTrue(score["gold_law_cited"])
        check = {"citations": [1], "ok": True, "refusal": False}
        self.assertFalse(score_answer(ITEM, answer, KEPT, check, NOTE)["gold_law_cited"])

    def test_closing_note_does_not_count_for_a_fact(self):
        item = {**ITEM, "key_facts": ["Το έτος 1999", "Το έτος 1999"]}
        self.assertEqual(score_answer(item, f"Κείμενο.\n\n{NOTE}", KEPT, {"citations": [], "ok": True, "refusal": False},
                                      NOTE)["fact_share"], 0)


def record(answerable=True, in_context=True, fact_share=1.0, refused=False):
    return {"answer": "…", "answerable": answerable, "times": {"model": 2.0}, "category": "single_source",
            "retrieval": {"in_context": in_context, "in_top_50": in_context, "reciprocal_rank": 1.0 if in_context else 0.0,
                          "gold_law_in_context": in_context, "semantic_rank": 1 if in_context else None,
                          "keyword_rank": None},
            "score": {"fact_share": fact_share if answerable else None, "refused": refused, "check_ok": True,
                      "gold_law_cited": in_context}}


class Problems(unittest.TestCase):
    def test_a_full_answer_is_no_problem(self):
        self.assertIsNone(problem(record()))

    def test_gold_chunk_missing_is_a_search_problem(self):
        self.assertEqual(problem(record(in_context=False, fact_share=0.0)), "search")

    def test_gold_chunk_there_but_facts_missing_is_a_reading_problem(self):
        self.assertEqual(problem(record(fact_share=0.5)), "reading")

    def test_refusing_when_the_gold_chunk_was_there_is_a_reading_problem(self):
        self.assertEqual(problem(record(refused=True)), "reading")

    def test_answering_an_unanswerable_question_is_a_reading_problem(self):
        self.assertEqual(problem(record(answerable=False)), "reading")
        self.assertIsNone(problem(record(answerable=False, refused=True)))

    def test_summary_counts(self):
        group = summarise_group([record(), record(in_context=False, fact_share=0.0), record(answerable=False, refused=True)])
        self.assertEqual((group["questions"], group["correct_refusals"], group["wrong_refusals"]), (3, 1, 0))
        self.assertEqual((group["search_problems"], group["reading_problems"]), (1, 0))
        self.assertEqual(group["fact_share"], 0.5)
        self.assertEqual(round(group["recall_at_8"], 2), 0.67)


class EvalSetChecks(unittest.TestCase):
    TEXT = "Άρθρ.3.-Για κάθε περίοδο 24 ωρών, η ελάχιστη ανάπαυση δεν μπορεί να είναι κατώτερη από 12 συνεχείς ώρες."

    def test_a_quote_may_skip_words_but_not_change_them(self):
        self.assertTrue(quote_in("η ελαχιστη αναπαυση … 12 συνεχείς ώρες", self.TEXT))
        self.assertFalse(quote_in("12 συνεχείς ώρες … η ελάχιστη ανάπαυση", self.TEXT))
        self.assertFalse(quote_in("11 συνεχείς ώρες", self.TEXT))

    def test_copied_wording_is_counted_in_whole_words(self):
        self.assertEqual(copied_run("Πόσες συνεχείς ώρες ξεκούραση;", self.TEXT), 2)
        self.assertEqual(copied_run("Η ελάχιστη ανάπαυση δεν μπορεί να είναι;", self.TEXT), 7)


if __name__ == "__main__":
    unittest.main()
