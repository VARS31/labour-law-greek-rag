"""Phase 3B parts that run without a database or model: reading the enhancer's answer, combining searches, the prompt check."""

import json
import unittest

from labour_rag.enhancer import PROMPT_FILE, law_keywords, parse_output, written_in_question
from labour_rag.evaluate import config_name, load_questions
from labour_rag.search import best_similarity
from scripts.check_enhancer_prompt import check, examples


def answer(**fields):
    return json.dumps({"rewritten": "Ερώτηση;", "variants": ["α", "β"], "law_refs": [], "topic_hint": "θέμα", **fields}, ensure_ascii=False)


def results(*pairs):
    return [{"id": i, "score": s, "rank": n} for n, (i, s) in enumerate(pairs, 1)]


class Output(unittest.TestCase):
    def test_a_good_answer(self):
        out = parse_output(answer(variants=[" α ", "β", "α"], law_refs=["Ν. 1837/1989", "άρθρο 2"]), "Τι λέει το άρθρο 2 του Ν. 1837/1989;")
        self.assertEqual((out["variants"], out["law_refs"], out["dropped_refs"], out["ok"]), (["α", "β"], ["Ν. 1837/1989", "άρθρο 2"], [], True))

    def test_at_most_three_variants(self):
        self.assertEqual(len(parse_output(answer(variants=list("αβγδε")), "Ερώτηση;")["variants"]), 3)

    def test_a_law_not_in_the_question_is_dropped(self):
        out = parse_output(answer(law_refs=["Αρ. 41/1980", "άρθρο 2"]), "Τι λέει το άρθρο 2 του Ν. 1837/1989;")
        self.assertEqual((out["law_refs"], out["dropped_refs"]), (["άρθρο 2"], ["Αρ. 41/1980"]))

    def test_a_search_phrase_with_a_law_not_in_the_question_is_dropped(self):
        out = parse_output(answer(variants=["άδεια κατά τον Ν.Δ. 146/1979", "ετήσια άδεια"]), "Ο εργοδότης αρνήθηκε την άδειά μου.")
        self.assertEqual((out["variants"], out["dropped_variants"]), (["ετήσια άδεια"], ["άδεια κατά τον Ν.Δ. 146/1979"]))

    def test_numbers_the_person_wrote_stay_in_a_search_phrase(self):
        out = parse_output(answer(variants=["εργασία ανηλίκου 15 ετών", "Ν. 2112/1920 άρθρο 3"]), "Παιδί 15 χρονών και άρθρο 3 του Ν. 2112/20;")
        self.assertEqual(out["dropped_variants"], [])

    def test_if_every_phrase_is_dropped_the_question_is_searched(self):
        out = parse_output(answer(variants=["νόμοι 1850-1999"]), "Η ερώτηση;")
        self.assertEqual(out["variants"], ["Η ερώτηση;"])

    def test_a_reference_without_numbers_is_dropped(self):
        self.assertEqual(parse_output(answer(law_refs=["Αστικός Κώδικας"]), "Τι ισχύει;")["law_refs"], [])

    def test_a_short_year_may_be_spelled_out(self):
        self.assertTrue(written_in_question("Ν. 2112/1920", "Τι λέει ο Ν. 2112/20;"))
        self.assertFalse(written_in_question("Ν. 2112/1921", "Τι λέει ο Ν. 2112/20;"))

    def test_an_unusable_answer_falls_back_to_the_question(self):
        for raw in ("όχι json", "{}", answer(variants=[]), answer(variants="κείμενο"), "[1, 2]"):
            out = parse_output(raw, "Η ερώτηση;")
            self.assertEqual((out["variants"], out["law_refs"], out["ok"]), (["Η ερώτηση;"], [], False), raw)

    def test_law_keywords_use_the_form_in_chunk_headers(self):
        self.assertEqual(law_keywords(["Ν. 1387/83", "άρθρο 6"]), "Ν. 1387/1983 άρθρο 6")


class Combining(unittest.TestCase):
    def test_a_chunk_keeps_its_best_similarity(self):
        fused = best_similarity([results(("a", 0.9), ("b", 0.5)), results(("b", 0.7), ("c", 0.6))])
        self.assertEqual([(r["id"], r["score"], r["rank"]) for r in fused], [("a", 0.9, 1), ("b", 0.7, 2), ("c", 0.6, 3)])

    def test_being_found_by_many_queries_earns_nothing(self):
        fused = best_similarity([results(("top", 0.9), ("common", 0.6)), results(("common", 0.6)), results(("common", 0.6))])
        self.assertEqual([r["id"] for r in fused], ["top", "common"])


class Names(unittest.TestCase):
    def test_a_run_through_the_enhancer_says_so(self):
        config = {"retrieval_only": True, "embedding": "qwen3-4b", "fusion": "semantic", "number_rule": "units",
                  "enhancer": "variants", "max_per_document": 2, "split": "dev"}
        self.assertEqual(config_name(config), "retrieval-qwen3-4b-enhancer-variants-units-limit2-dev")


class PromptCheck(unittest.TestCase):
    ITEMS = [{"id": "x", "question": "Πόσες μέρες άδεια δικαιούμαι;", "key_facts": ["Είκοσι τέσσερις ημέρες"], "notes": "Για τον Ν. 2112/1920.",
              "gold_sources": [{"law": "Α.Ν. 539/1945", "quote": "δικαιούται άδεια"}]}]

    def prompt(self, question, topic, refs=()):
        example = {"rewritten": question, "variants": ["α", "β"], "law_refs": list(refs), "topic_hint": topic}
        return f"Ερώτηση: {question}\nJSON: {json.dumps(example, ensure_ascii=False)}\n"

    def test_the_real_prompt_passes_against_the_real_test_set(self):
        problems, rows = check(PROMPT_FILE.read_text(encoding="utf-8"), load_questions())
        self.assertEqual(problems, [])
        self.assertGreaterEqual(len(rows), 3)

    def test_examples_in_the_prompt_are_found(self):
        self.assertEqual(examples(self.prompt("Μια ερώτηση;", "θέμα"))[0][0], "Μια ερώτηση;")

    def test_a_topic_from_the_test_set_is_caught(self):
        problems, _ = check(self.prompt("Τι ισχύει για στολές;", "άδεια"), self.ITEMS)
        self.assertTrue(any("topic word" in p for p in problems))

    def test_a_law_from_the_test_set_is_caught(self):
        problems, _ = check(self.prompt("Τι λέει ο Ν. 2112/1920;", "στολή", ["Ν. 2112/1920"]), self.ITEMS)
        self.assertTrue(any("law number 2112" in p for p in problems))

    def test_a_question_too_close_to_a_test_question_is_caught(self):
        problems, _ = check(self.prompt("Πόσες μέρες άδεια;", "στολή"), self.ITEMS)
        self.assertTrue(any("shares" in p for p in problems))

    def test_an_example_that_invents_a_law_is_caught(self):
        problems, _ = check(self.prompt("Τι ισχύει για στολές;", "στολή", ["Ν. 9999/1999"]), self.ITEMS)
        self.assertTrue(any("own rules" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
