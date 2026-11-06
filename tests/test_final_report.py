"""How failures are shared out between the steps in the final report."""

import unittest

from scripts.final_report import EVIDENCE, READ, SPLITS, SYSTEMS, WRONG_THOUGH_COMPLETE, failure_of


def record(item="single-01", fact_share=1.0, refused=False, answerable=True, in_context=True, gold_judged=True):
    return {"id": item, "answer": "…", "answerable": answerable,
            "score": {"fact_share": fact_share, "refused": refused},
            "retrieval": {"in_context": in_context, "gold_judged": gold_judged}}


class FailureOfOneShot(unittest.TestCase):
    def test_a_complete_answer_is_no_failure(self):
        self.assertIsNone(failure_of("oneshot-v2", record(), {}))

    def test_read_as_wrong_with_the_right_chunk_is_the_writers(self):
        self.assertEqual(failure_of("oneshot-v2", record(), {"single-01": "reason"}), "writer")

    def test_read_as_wrong_without_the_right_chunk_is_searchs(self):
        # v2's lookup-01: the matcher took a list number for a key fact, and the right chunk wasn't among the 8.
        self.assertEqual(failure_of("oneshot-v2", record(in_context=False), {"single-01": "reason"}), "search")

    def test_answering_what_should_be_refused_is_the_writers_without_a_judge(self):
        for system in ("baseline", "oneshot-v2", "oneshot-haiku"):
            self.assertEqual(failure_of(system, record(answerable=False, fact_share=None, in_context=False), {}), "writer")


class FailureOfAgent(unittest.TestCase):
    def test_read_as_wrong_with_the_right_chunk_is_the_writers(self):
        for system in ("agent", "agent-haiku"):
            self.assertEqual(failure_of(system, record(), {"single-01": "reason"}), "writer")

    def test_held_back_by_the_judge(self):
        for system in ("agent", "agent-haiku"):
            self.assertEqual(failure_of(system, record(fact_share=0.0, refused=True, in_context=False), {}), "judge")

    def test_never_reached_the_judge(self):
        for system in ("agent", "agent-haiku"):
            self.assertEqual(failure_of(system, record(fact_share=0.0, in_context=False, gold_judged=False), {}), "search")

    def test_answering_what_should_be_refused_is_the_judges(self):
        for system in ("agent", "agent-haiku"):
            self.assertEqual(failure_of(system, record(answerable=False, fact_share=None), {}), "judge")


class Verdicts(unittest.TestCase):
    def test_every_fail_has_a_reason_and_words_it_rests_on(self):
        for (system, split), wrong in WRONG_THOUGH_COMPLETE.items():
            for item, reason in wrong.items():
                self.assertTrue(reason, item)
                self.assertIn((system, split, item), EVIDENCE)

    def test_a_verdict_stands_when_both_readers_agree_and_is_ruled_only_when_they_differ(self):
        for split in SPLITS:
            for system in SYSTEMS:
                for item, entry in READ[split][system].items():
                    agreed = entry["reader_a"]["verdict"] == entry["reader_b"]["verdict"]
                    self.assertEqual(entry["ruled"], not agreed, item)
                    if agreed:
                        self.assertEqual(entry["verdict"], entry["reader_a"]["verdict"], item)


if __name__ == "__main__":
    unittest.main()
