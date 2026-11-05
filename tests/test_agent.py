"""Phase 3C: the agent's graph and the Judge, with the database and the models replaced, so the routing can be tested on its own."""

import json
import unittest
from unittest import mock

import langsmith.utils

from labour_rag import agent, enhancer, judge, search
from labour_rag.agent import MAX_ROUNDS, missing_sentences, refusal_text
from labour_rag.ask import closing_note
from labour_rag.evaluate import agent_problem, config_name
from labour_rag.law_mentions import law_references, names_a_law


WORDS = "άδεια μισθός απόλυση σύμβαση εργάτης ημέρα ωράριο ταμείο βιβλίο όροφος κτίριο δρόμος γέφυρα πλοίο λιμάνι".split()


def chunk(n, year=1980, doc=None, text=None, citation=None):
    return {"id": f"glc-{doc or n:05d}-000", "doc_id": doc or n, "n": n, "rank": n, "semantic_rank": n, "keyword_rank": None, "citation": citation or f"Υ.Α. {n}/{year}",
            "citation_fallback": False, "article": f"Άρθρο {n}", "title": "", "year": year, "is_note": False, "is_stub": False, "score": 1 - n / 100,
            "text": text or f"{WORDS[n]} {WORDS[n]}ς {WORDS[n]}ν"}      # different words, so that no two chunks count as repeats


def verdict(n, relevance="relevant", applies="yes", replaced_by=0):
    return {"n": n, "relevance": relevance, "applies": applies, "only_for": "", "replaced_by": replaced_by, "reason": "λόγος"}


def judged(verdicts, decision="answer", missing="", references=()):
    return json.dumps({"chunks": verdicts, "decision": decision, "missing": missing, "references": list(references)}, ensure_ascii=False)


ENHANCED = {"rewritten": "ΑΥΤΗ ΔΕΝ ΠΡΕΠΕΙ ΝΑ ΦΤΑΣΕΙ ΣΤΟΝ ΣΥΓΓΡΑΦΕΑ", "variants": ["φράση α", "φράση β"], "law_refs": [], "topic_hint": "θέμα", "dropped_refs": [],
            "dropped_variants": [], "ok": True, "seconds": 7.0, "raw": "{}", "tokens": {}}


class FakeClient:
    """Answers the Judge's calls from a script, and the writer with a fixed sentence. Keeps every message."""
    chat_model = "fake"
    last_chat = {}

    def __init__(self, judge_answers):
        self.judge_answers = list(judge_answers)
        self.calls = []

    def chat(self, messages, response_format=None, **options):
        self.calls.append({"messages": messages, "format": response_format, "options": options})
        if response_format:
            return self.judge_answers.pop(0)
        return "Η απάντηση από το 1980 [1]."

    def writer_message(self):
        return next(c for c in self.calls if not c["format"])["messages"][1]["content"]


class GraphCase(unittest.TestCase):
    """Rounds 1 to 3 find chunks 1-2, 3-4 and 5-6 unless a test says otherwise."""

    def run_agent(self, *answers, law_found=True, keyword=(), near=()):
        client = FakeClient(answers)
        lists = [[chunk(1), chunk(2)], [chunk(3), chunk(4)], [chunk(5), chunk(6)]]

        def multi_query(conn, client, queries, keyword_query="", k=10, embedding=None):
            found = lists.pop(0)
            self.queries.append(queries)
            return found, {"semantic": found, "keyword": []}

        self.queries = []
        with (mock.patch.object(search, "multi_query", multi_query), mock.patch.object(search, "keyword", lambda *a: list(keyword)),
              mock.patch.object(search, "neighbours", lambda *a: list(near)), mock.patch.object(enhancer, "enhance", lambda *a: ENHANCED),
              mock.patch.object(agent, "law_in_data", lambda conn, law: law_found)):
            result = agent.run(None, client, "Η ερώτηση του ανθρώπου;")
        return result, client


class Graph(GraphCase):
    def test_an_answer_in_the_first_round(self):
        result, client = self.run_agent(judged([verdict(1), verdict(2, "not_relevant")]))
        self.assertEqual(len(result["rounds"]), 1)
        self.assertEqual([c["id"] for c in result["chunks"]], ["glc-00001-000"])
        self.assertEqual(result["chunks"][0]["n"], 1)
        self.assertFalse(result["refused_by_judge"])
        self.assertEqual(self.queries, [["Η ερώτηση του ανθρώπου;"]])

    def test_the_writer_sees_only_approved_chunks_and_the_persons_own_question(self):
        _, client = self.run_agent(judged([verdict(1, "not_relevant"), verdict(2, "partly")], "search_again", "λείπει"), judged([verdict(1), verdict(2, "partly"), verdict(3, "not_relevant")]))     # renumbered each round: [1] is chunk 2
        message = client.writer_message()
        self.assertIn("Η ερώτηση του ανθρώπου;", message)
        self.assertNotIn("ΔΕΝ ΠΡΕΠΕΙ", message)
        self.assertIn("Υ.Α. 2/1980", message)
        self.assertIn("Υ.Α. 3/1980", message)
        self.assertNotIn("Υ.Α. 4/1980", message)

    def test_round_two_searches_the_variants_and_never_shows_a_rejected_chunk_again(self):
        result, client = self.run_agent(judged([verdict(1, "not_relevant"), verdict(2, "partly")], "search_again", "λείπει"), judged([verdict(1), verdict(2), verdict(3)]))
        self.assertEqual(self.queries[1], ["φράση α", "φράση β"])
        shown = [c["id"] for c in result["rounds"][1]["chunks"]]
        self.assertNotIn("glc-00001-000", shown)
        self.assertIn("glc-00002-000", shown)        # approved: stays in front of the Judge
        self.assertIn("glc-00003-000", shown)
        self.assertIn("variant: φράση α", result["rounds"][1]["searched"])

    def test_the_judge_is_asked_at_temperature_zero(self):
        _, client = self.run_agent(judged([verdict(1), verdict(2)]))
        self.assertEqual(client.calls[0]["options"]["temperature"], 0)

    def test_at_most_three_rounds_and_the_last_cant_search_again(self):
        again = judged([verdict(1, "not_relevant"), verdict(2, "not_relevant")], "search_again", "λείπει")
        result, client = self.run_agent(again, again, judged([verdict(5, "not_relevant"), verdict(6, "not_relevant")], "refuse", "τίποτα"))
        self.assertEqual(len(result["rounds"]), MAX_ROUNDS)
        self.assertNotIn("search_again", client.calls[2]["format"]["properties"]["decision"]["enum"])
        self.assertIn("search_again", client.calls[0]["format"]["properties"]["decision"]["enum"])
        self.assertTrue(result["refused_by_judge"])

    def test_round_three_searches_what_the_judge_said_was_missing(self):
        again = judged([verdict(1, "not_relevant"), verdict(2, "not_relevant")], "search_again", "το ποσοστό της προσαύξησης")
        self.run_agent(again, again, judged([verdict(5), verdict(6)]))
        self.assertEqual(self.queries[2], ["το ποσοστό της προσαύξησης", "φράση α", "φράση β"])

    def test_answer_without_an_approved_chunk_searches_again(self):
        result, _ = self.run_agent(judged([verdict(1, "not_relevant"), verdict(2, "not_relevant")], "answer"), judged([verdict(3), verdict(4)]))
        self.assertEqual(len(result["rounds"]), 2)

    def test_a_refusal_is_written_by_the_code_and_calls_no_writer(self):
        result, client = self.run_agent(judged([verdict(1, "not_relevant"), verdict(2, "not_relevant")], "refuse", "εκτός θέματος"))
        self.assertTrue(result["refused_by_judge"])
        self.assertEqual(result["chunks"], [])
        self.assertTrue(result["check"]["refusal"])
        self.assertTrue(result["check"]["ok"])
        self.assertIn(closing_note(), result["answer"])
        self.assertEqual(len(client.calls), 1)

    def test_a_missing_law_the_judge_named_is_said_in_the_refusal_and_in_an_answer(self):
        chunks = [verdict(1, "not_relevant"), verdict(2, "not_relevant")]
        with mock.patch.object(agent, "normalize", lambda q: q):
            result, _ = self.run_agent(judged(chunks, "refuse", "λείπει", ["Ν. 435/1976"]), law_found=False)
        self.assertEqual(result["laws_missing"], [])        # not written in any chunk: the model's memory, so it doesn't count
        text = "Το ποσοστό βλ. Νόμ. 435/1976."
        client = FakeClient([judged([verdict(1)], "answer", "", ["Νόμ. 435/1976"])])
        with (mock.patch.object(search, "multi_query", lambda *a, **k: ([chunk(1, text=text)], {"semantic": [], "keyword": []})),
              mock.patch.object(agent, "law_in_data", lambda conn, law: False)):
            answered = agent.run(None, client, "Η ερώτηση;")
        self.assertEqual(answered["laws_missing"], ["Ν. 435/1976"])
        self.assertIn("παραπέμπουν στον Ν. 435/1976, αλλά το κείμενό του δεν υπάρχει", answered["answer"])
        self.assertTrue(answered["answer"].endswith(closing_note()))

    def test_a_law_in_our_data_is_searched_by_keyword_once(self):
        text = "Για τον κανόνα βλ. Νόμ. 2112/1920."
        named = chunk(1, text=text)
        extra = chunk(9)
        calls = []

        def keyword(conn, query, k):
            calls.append(query)
            return [extra]

        client = FakeClient([judged([verdict(1, "partly")], "search_again", "λείπει", ["Νόμ. 2112/1920"]), judged([verdict(1, "partly"), verdict(2, "partly")], "search_again", "λείπει", ["Νόμ. 2112/1920"]),
                             judged([verdict(1), verdict(2)])])
        lists = [[named], [chunk(2)], [chunk(3)]]
        with (mock.patch.object(search, "multi_query", lambda *a, **k: (lists.pop(0), {"semantic": [], "keyword": []})), mock.patch.object(search, "keyword", keyword),
              mock.patch.object(search, "neighbours", lambda *a: []), mock.patch.object(enhancer, "enhance", lambda *a: ENHANCED), mock.patch.object(agent, "law_in_data", lambda c, l: True)):
            result = agent.run(None, client, "Η ερώτηση;")
        self.assertEqual(calls, ["Ν. 2112/1920"])
        self.assertIn("glc-00009-000", [c["id"] for c in result["rounds"][1]["chunks"]])

    def test_neighbours_of_approved_chunks_are_shown_even_over_the_limit(self):
        near = [{**chunk(1, doc=1), "id": f"glc-00001-00{i}", "n": 0} for i in (1, 2, 3)]
        result, _ = self.run_agent(judged([verdict(1, "partly"), verdict(2, "not_relevant")], "search_again", "λείπει"), judged([verdict(1)]), near=near)
        round_two = result["rounds"][1]["chunks"]
        neighbours = [c for c in round_two if c["source"].startswith("next to")]
        self.assertEqual([c["id"] for c in neighbours], ["glc-00001-001", "glc-00001-002"])

    def test_every_round_is_recorded(self):
        result, _ = self.run_agent(judged([verdict(1, "partly"), verdict(2, "partly")], "search_again", "λείπει"), judged([verdict(1), verdict(2), verdict(3)]))
        record = result["rounds"][0]
        self.assertEqual(record["decision"], "search_again")
        self.assertEqual(record["missing"], "λείπει")
        self.assertEqual(record["approved"], ["glc-00001-000", "glc-00002-000"])
        self.assertEqual(record["verdicts"][0]["reason"], "λόγος")
        self.assertIn("judge", record["seconds"])
        self.assertIn("enhancer", result["rounds"][1]["seconds"])
        self.assertIn("enhancer", result["times"])
        self.assertNotIn("text", record["chunks"][0])


class TheTwoFixes(GraphCase):
    """Phase 3C.1: stop when a right chunk is in hand, and read further down the plain list in round 2."""

    LONG = 20       # how many chunks the plain question's list has in these tests

    def run_long(self, *answers, removed=()):
        client = FakeClient(answers)
        lists = [[chunk(i % 14 + 1, doc=i, text=f"λέξη{'αβγδεζηθικλμνξοπρστυφχψω'[i]}ο άλλη{'αβγδεζηθικλμνξοπρστυφχψω'[i]}ο") for i in range(self.LONG)],
                 [chunk(14, doc=100, citation="Από φράση")], [chunk(14, doc=101, citation="Από έλλειψη")]]
        for n, c in enumerate(lists[0], 1):
            c["rank"] = n

        def multi_query(conn, client, queries, keyword_query="", k=10, embedding=None):
            found = lists.pop(0)
            return found, {"semantic": found, "keyword": []}

        real_select = agent.select

        def select_with_removed(results, k, limit):
            kept, gone = real_select(results, k, limit)
            return kept, gone + [{**r, "reason": "near-duplicate", "of": None} for r in results if r["id"] in removed]

        with (mock.patch.object(search, "multi_query", multi_query), mock.patch.object(search, "keyword", lambda *a: []), mock.patch.object(search, "neighbours", lambda *a: []),
              mock.patch.object(enhancer, "enhance", lambda *a: ENHANCED), mock.patch.object(agent, "law_in_data", lambda c, l: True), mock.patch.object(agent, "select", select_with_removed)):
            return agent.run(None, client, "Η ερώτηση;"), client

    def test_stops_when_an_approved_chunk_answers_directly(self):
        result, client = self.run_agent(judged([verdict(1), verdict(2, "not_relevant")], "search_again", "θέλω κι άλλα"))
        self.assertEqual(len(result["rounds"]), 1)
        self.assertEqual(result["rounds"][0]["decision"], "search_again")     # what the Judge said stays on record
        self.assertTrue(result["rounds"][0]["stopped_by_code"])
        self.assertFalse(result["refused_by_judge"])
        self.assertEqual([c["id"] for c in result["chunks"]], ["glc-00001-000"])

    def test_a_partly_relevant_or_unclear_chunk_doesnt_stop_the_search(self):
        for first in (verdict(1, "partly"), verdict(1, "relevant", "unclear")):
            result, _ = self.run_agent(judged([first, verdict(2, "not_relevant")], "search_again", "λείπει"), judged([verdict(1), verdict(2), verdict(3)]))
            self.assertEqual(len(result["rounds"]), 2, first)
            self.assertFalse(result["rounds"][0]["stopped_by_code"])

    def test_a_chunk_replaced_by_a_newer_act_doesnt_stop_the_search(self):
        client = FakeClient([judged([verdict(1, replaced_by=2), verdict(2, "partly")], "search_again", "λείπει"), judged([verdict(1)])])
        lists = [[chunk(1, 1950), chunk(2, 1990)], [chunk(3)]]
        with (mock.patch.object(search, "multi_query", lambda *a, **k: (lists.pop(0), {"semantic": [], "keyword": []})), mock.patch.object(search, "keyword", lambda *a: []),
              mock.patch.object(search, "neighbours", lambda *a: []), mock.patch.object(enhancer, "enhance", lambda *a: ENHANCED)):
            self.assertEqual(len(agent.run(None, client, "Ε;")["rounds"]), 2)

    def test_it_doesnt_overrule_a_refusal(self):
        result, _ = self.run_agent(judged([verdict(1), verdict(2)], "refuse", "εκτός θέματος"))
        self.assertTrue(result["refused_by_judge"])

    def test_round_two_reads_the_next_places_of_the_plain_list(self):
        nothing = [verdict(n, "not_relevant") for n in range(1, 21)]
        result, _ = self.run_long(judged(nothing[:8], "search_again", "λείπει"), judged(nothing[:12], "search_again", "λείπει"), judged(nothing[:8], "refuse", "τίποτα"))
        round_two = result["rounds"][1]
        self.assertEqual(round_two["searched"][0], "the question, further down its list: ranks 9 to 16")
        self.assertEqual([c["source"] for c in round_two["chunks"]][:8], [f"question, rank {n}" for n in range(9, 17)])
        self.assertEqual(round_two["chunks"][8]["source"], "variants")
        self.assertLessEqual(len(round_two["chunks"]), agent.ROUND_2_CHUNKS)

    def test_round_three_doesnt_read_the_plain_list_any_further(self):
        nothing = [verdict(n, "not_relevant") for n in range(1, 21)]
        result, _ = self.run_long(judged(nothing[:8], "search_again", "λείπει"), judged(nothing[:12], "search_again", "λείπει"), judged(nothing[:8], "refuse", "τίποτα"))
        self.assertFalse(any(c["source"].startswith("question") for c in result["rounds"][2]["chunks"]))
        self.assertFalse(any(s.startswith("the question") for s in result["rounds"][2]["searched"]))

    def test_chunks_removed_as_repeats_in_round_one_arent_read_again(self):
        nothing = [verdict(n, "not_relevant") for n in range(1, 21)]
        removed = {"glc-00010-000"}
        result, _ = self.run_long(judged(nothing[:8], "search_again", "λείπει"), judged(nothing[:12], "refuse", "τίποτα"), removed=removed)
        self.assertNotIn("glc-00010-000", [c["id"] for c in result["rounds"][1]["chunks"]])


class Trace(unittest.TestCase):
    def test_the_trace_shows_every_step(self):
        record = {"round": 2, "seconds": {"judge": 44.5}, "searched": ["the question"], "laws_named": ["Ν. 435/1976"], "decision": "search_again", "missing": "λείπει", "approved": ["a"],
                  "chunks": [{"n": 1, "id": "a", "citation": "Ν. 1/1950", "article": None, "source": "question"}, {"n": 2, "id": "b", "citation": "Ν. 2/1950", "article": "Άρθρο 2", "source": "variants"}],
                  "verdicts": [{"n": 1, "relevance": "relevant", "applies": "yes", "only_for": "", "replaced_by": 0, "reason": "απαντά"},
                               {"n": 2, "relevance": "partly", "applies": "no", "only_for": "ναυτικοί", "replaced_by": 1, "reason": "άλλη ομάδα"}]}
        text = "\n".join(agent.trace_lines([record]))
        for part in ("ROUND 2", "judge 44.5 s", "the question", "[1] approved", "[2] rejected", "only for: ναυτικοί", "replaced by [1]", "άλλη ομάδα", "DECISION: search_again. Missing: λείπει", "LAWS NAMED: Ν. 435/1976"):
            self.assertIn(part, text)
        self.assertNotIn("STOPPED", text)
        self.assertIn("STOPPED BY THE CODE", "\n".join(agent.trace_lines([{**record, "stopped_by_code": True}])))


class Judge(unittest.TestCase):
    CHUNKS = [chunk(1, 1989), chunk(2, 1997), chunk(3, None)]

    def parse(self, *verdicts, **fields):
        return judge.parse_output(judged(list(verdicts), **fields), self.CHUNKS)

    def ids(self, result):
        return [c["n"] for c in judge.approved(self.CHUNKS, result)]

    def test_not_relevant_and_not_applying_are_filtered(self):
        result = self.parse(verdict(1), verdict(2, "not_relevant"), verdict(3, "relevant", "no"))
        self.assertEqual(self.ids(result), [1])

    def test_relevant_comes_before_partly(self):
        self.assertEqual(self.ids(self.parse(verdict(1, "partly"), verdict(2), verdict(3, "partly"))), [2, 1, 3])

    def test_a_chunk_replaced_by_a_newer_act_goes(self):
        self.assertEqual(self.ids(self.parse(verdict(1, replaced_by=2), verdict(2), verdict(3, "not_relevant"))), [2])

    def test_replaced_by_an_older_act_is_ignored(self):
        self.assertEqual(self.ids(self.parse(verdict(1), verdict(2, replaced_by=1), verdict(3, "not_relevant"))), [1, 2])

    def test_replaced_by_a_chunk_that_isnt_approved_or_has_no_year_is_ignored(self):
        self.assertEqual(self.ids(self.parse(verdict(1, replaced_by=2), verdict(2, "not_relevant"), verdict(3, "not_relevant"))), [1])
        self.assertEqual(self.ids(self.parse(verdict(1, replaced_by=3), verdict(2, "not_relevant"), verdict(3))), [1, 3])

    def test_a_skipped_chunk_is_kept(self):
        result = self.parse(verdict(1, "not_relevant"), verdict(3, "not_relevant"))
        self.assertEqual((self.ids(result), result["skipped"]), ([2], [2]))

    def test_an_unreadable_answer_keeps_everything_and_goes_on(self):
        for raw in ("όχι json", "{}", json.dumps({"chunks": [], "decision": "maybe", "references": []})):
            result = judge.parse_output(raw, self.CHUNKS)
            self.assertEqual((result["decision"], result["ok"]), ("answer", False), raw)
            self.assertEqual(len(judge.approved(self.CHUNKS, result)), 3)

    def test_the_last_round_cant_search_again(self):
        self.assertFalse(judge.parse_output(judged([], "search_again"), self.CHUNKS, final_round=True)["ok"])

    def test_a_law_must_be_written_in_the_chunks(self):
        chunks = [chunk(1, text="Για τις υπερωρίες βλ. Νόμ. 435/1976.")]
        kept, dropped = judge.named_laws(["Νόμ. 435/1976", "Ν. 9999/1950", "ο αστικός κώδικας"], chunks)
        self.assertEqual(kept, ["Ν. 435/1976"])
        self.assertIn("Ν. 9999/1950", dropped)

    def test_a_decree_cited_by_its_date_is_not_a_law_number(self):
        chunks = [chunk(1, text="Κατά το Β.Δ. 16/18 Ιουλ. 1920 περί επεκτάσεως.")]
        self.assertEqual(judge.named_laws(["Β.Δ. 16/1920"], chunks), ([], ["Β.Δ. 16/1920"]))

    def test_a_law_written_with_a_short_year_is_the_same_law(self):
        chunks = [chunk(1, text="Για τις υπερωρίες βλ. Νόμ. 435/76.")]
        self.assertEqual(judge.named_laws(["Ν. 435/1976"], chunks), (["Ν. 435/1976"], []))

    def test_text_is_only_cut_when_many_chunks_are_shown(self):
        long_text = " ".join(["λέξη"] * 500)
        eight = [chunk(i, text=long_text) for i in range(1, 9)]
        self.assertNotIn("…", judge.user_message("Ερώτηση;", eight, 1, 3))
        sixteen = [chunk(i, text=long_text) for i in range(1, 17)]
        self.assertIn("…", judge.user_message("Ερώτηση;", sixteen, 2, 3))

    def test_the_last_round_says_so(self):
        self.assertIn("τελευταίος", judge.user_message("Ε;", self.CHUNKS[:1], 3, 3))
        self.assertNotIn("τελευταίος", judge.user_message("Ε;", self.CHUNKS[:1], 2, 3))


class Refusals(unittest.TestCase):
    def test_a_refusal_names_where_the_rule_would_be(self):
        text = refusal_text([], ["Π.Δ. 80/1960"], ["Ν. 435/1976"])
        self.assertTrue(text.startswith("**Σύντομη απάντηση:** Δεν βρέθηκε"))
        self.assertIn("παραπέμπουν στον Ν. 435/1976, αλλά το κείμενό του δεν υπάρχει", text)
        self.assertIn("παραπέμπουν στο Π.Δ. 80/1960.", text)

    def test_a_law_the_person_asked_about(self):
        self.assertEqual(missing_sentences(["Ν. 4808/2021"], ["Ν. 4808/2021"]), ["Το κείμενο του Ν. 4808/2021 δεν υπάρχει στα διαθέσιμα κείμενα."])


class Questions(unittest.TestCase):
    def test_laws_and_articles_a_question_names(self):
        self.assertEqual(law_references("Τι λέει το άρθρο 2 του Ν. 1837/89;"), ["Ν. 1837/1989", "άρθρο 2"])
        self.assertEqual(law_references("Πόσες μέρες άδεια έχω;"), [])
        self.assertTrue(names_a_law("Τι ορίζει το άρθρο 5;"))


class Local(unittest.TestCase):
    def test_tracing_stays_off(self):
        self.assertFalse(langsmith.utils.tracing_is_enabled())


class Labels(unittest.TestCase):
    def record(self, answerable=True, fact_share=0.5, refused=False, judged_gold=True, in_context=True):
        return {"answerable": answerable, "score": {"fact_share": fact_share, "refused": refused},
                "retrieval": {"gold_judged": judged_gold, "in_context": in_context}}

    def test_labels(self):
        self.assertEqual(agent_problem(self.record(judged_gold=False, in_context=False)), "search")
        self.assertEqual(agent_problem(self.record(in_context=False)), "judge")
        self.assertEqual(agent_problem(self.record()), "writer")
        self.assertIsNone(agent_problem(self.record(fact_share=1)))
        self.assertEqual(agent_problem(self.record(fact_share=1, refused=True, in_context=False)), "judge")
        self.assertEqual(agent_problem(self.record(answerable=False)), "judge")
        self.assertIsNone(agent_problem(self.record(answerable=False, refused=True)))

    def test_run_name(self):
        config = {"system": "agent", "retrieval_only": False, "embedding": "qwen3-4b", "fusion": "semantic", "number_rule": "units", "max_per_document": 4, "split": "dev"}
        self.assertEqual(config_name(config), "agent-qwen3-4b-semantic-units-limit4-dev")


class PromptExample(unittest.TestCase):
    def test_the_judges_example_is_off_the_test_set(self):
        import re

        from labour_rag.evaluate import load_questions
        from labour_rag.key_facts import _word_found
        from scripts.check_enhancer_prompt import MAX_SHARE, item_text, words

        prompt = judge.PROMPT_FILE.read_text(encoding="utf-8")
        topic = re.search(r"Παράδειγμα \(θέμα: (.+)\):", prompt).group(1)
        example = prompt[prompt.index("Παράδειγμα (θέμα"):]
        question = re.search(r"Ερώτηση: (.+)", example).group(1)
        items = load_questions()
        texts = {i["id"]: item_text(i) for i in items}
        for word in words(topic):
            self.assertEqual([i for i, t in texts.items() if _word_found(word, words(t))], [], word)
        for number in [n for n in re.findall(r"\d{3,}", example) if not re.fullmatch(r"1[89]\d\d", n)]:     # a year is no topic
            self.assertEqual([i for i, t in texts.items() if re.search(rf"(?<!\d){number}(?!\d)", t)], [], number)
        own = words(question)
        for item in items:
            shared = {w for w in own if _word_found(w, words(item["question"]))}
            self.assertLessEqual(len(shared) / len(own), MAX_SHARE, item["id"])


if __name__ == "__main__":
    unittest.main()
