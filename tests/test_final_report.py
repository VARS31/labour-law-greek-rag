"""How failures are shared out between the steps in the final report."""

import unittest

from scripts.final_report import NOTED, WRONG_THOUGH_COMPLETE, failure_of


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
        self.assertEqual(failure_of("baseline", record(answerable=False, fact_share=None, in_context=False), {}), "writer")


class FailureOfAgent(unittest.TestCase):
    def test_read_as_wrong_with_the_right_chunk_is_the_writers(self):
        self.assertEqual(failure_of("agent", record(), {"single-01": "reason"}), "writer")

    def test_held_back_by_the_judge(self):
        self.assertEqual(failure_of("agent", record(fact_share=0.0, refused=True, in_context=False), {}), "judge")

    def test_never_reached_the_judge(self):
        self.assertEqual(failure_of("agent", record(fact_share=0.0, in_context=False, gold_judged=False), {}), "search")

    def test_answering_what_should_be_refused_is_the_judges(self):
        self.assertEqual(failure_of("agent", record(answerable=False, fact_share=None), {}), "judge")


class Verdicts(unittest.TestCase):
    def test_an_answer_that_fails_is_not_also_noted(self):
        for system, notes in NOTED.items():
            self.assertFalse(set(notes) & set(WRONG_THOUGH_COMPLETE[system, "test"]), system)


if __name__ == "__main__":
    unittest.main()
