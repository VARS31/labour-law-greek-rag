"""The Haiku client and the budget guard, with a stand-in for the SDK: no test makes a real call or needs a key."""

import argparse
import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import anthropic

from labour_rag import agent, ask, budget, enhancer, evaluate, haiku_runs, judge
from labour_rag.budget import LONG_RATES, RUN_LIMIT, SHORT_PROMPT, SHORT_RATES, TOTAL_LIMIT, Budget, BudgetExceeded, call_cost
from labour_rag.haiku_client import MAX_TOKENS, MODEL, HaikuClient, strict_schema
from labour_rag.haiku_runs import MANUAL_LEDGER, MANUAL_LIMIT, MixedClient, check_key, client_for, failure_text, manual_run
from labour_rag.model_client import ModelError

SYSTEM = {"role": "system", "content": "οδηγίες"}
USER = {"role": "user", "content": "Ερώτηση"}


def reply(text="απάντηση", stop_reason="end_turn", input_tokens=1000, output_tokens=200, thinking=False):
    blocks = ([SimpleNamespace(type="thinking", thinking="")] if thinking else []) + [SimpleNamespace(type="text", text=text)]
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens, cache_creation_input_tokens=None, cache_read_input_tokens=None,
                            output_tokens_details=SimpleNamespace(thinking_tokens=150 if thinking else 0))
    return SimpleNamespace(content=blocks, usage=usage, stop_reason=stop_reason, model=MODEL)


class FakeSDK:
    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []
        self.messages = SimpleNamespace(create=self.create)
        self.models = SimpleNamespace(retrieve=self.retrieve)
        self.refuse_with = None
        self.key_checks = 0

    def retrieve(self, model):
        self.key_checks += 1
        if self.refuse_with:
            raise self.refuse_with

    def create(self, **request):
        self.requests.append(request)
        return self.replies.pop(0)


class FakeLocal:
    def __init__(self):
        self.calls, self.last_chat = [], {"prompt_tokens": 7, "answer_tokens": 8}

    def chat(self, messages, response_format=None, **options):
        self.calls.append((messages, response_format, options))
        return '{"local": true}'

    def embed(self, texts, model=None, dim=None):
        return [[0.5] for _ in texts]


class WithLedger(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "spend.json"

    def budget(self, run="run-a", **limits):
        return Budget(run, self.path, **limits)


class Costs(unittest.TestCase):
    def test_the_published_rates(self):
        self.assertAlmostEqual(call_cost(100_000, 0), 0.01)
        self.assertAlmostEqual(call_cost(0, 1_000_000), 0.50)
        self.assertAlmostEqual(call_cost(10_000, 2_000), 0.002)

    def test_a_long_prompt_costs_more_for_the_whole_call(self):
        self.assertAlmostEqual(call_cost(SHORT_PROMPT, 1000), (SHORT_PROMPT * SHORT_RATES[0] + 1000 * SHORT_RATES[1]) / 1e6)
        self.assertAlmostEqual(call_cost(SHORT_PROMPT + 1, 1000), ((SHORT_PROMPT + 1) * LONG_RATES[0] + 1000 * LONG_RATES[1]) / 1e6)

    def test_cached_tokens_count_towards_the_cost_and_the_prompt_length(self):
        self.assertAlmostEqual(call_cost(100, 0, cache_read=1000), (100 + 100) * SHORT_RATES[0] / 1e6)
        self.assertAlmostEqual(call_cost(0, 0, cache_read=SHORT_PROMPT + 1), (SHORT_PROMPT + 1) * LONG_RATES[0] * 0.1 / 1e6)


class TheGuard(WithLedger):
    def test_the_limits_the_owner_set(self):
        self.assertEqual((RUN_LIMIT, TOTAL_LIMIT), (1.00, 3.00))

    def test_the_total_is_kept_on_disk_and_a_resumed_run_counts_it(self):
        self.budget().add(0.40, 1000, 100)
        resumed = self.budget()
        self.assertEqual(resumed.spent(), (0.40, 0.40))
        resumed.add(0.10, 500, 50)
        ledger = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(ledger["runs"]["run-a"], {"spent": 0.5, "calls": 2, "input_tokens": 1500, "output_tokens": 150})
        self.assertEqual(ledger["total"], 0.5)

    def test_a_run_stops_at_its_limit(self):
        self.budget().add(0.99, 1, 1)
        self.budget().check(0.01)
        with self.assertRaises(BudgetExceeded):
            self.budget().check(0.011)

    def test_the_total_counts_every_run(self):
        for run in ("a", "b", "c"):
            self.budget(run).add(0.99, 1, 1)
        with self.assertRaisesRegex(BudgetExceeded, "all runs"):
            self.budget("d").check(0.04)

    def test_no_half_written_file_stays_behind(self):
        self.budget().add(0.01, 1, 1)
        self.assertEqual([p.name for p in self.path.parent.iterdir()], [self.path.name])


class TheClient(WithLedger):
    def client(self, *replies, **limits):
        self.local, self.sdk = FakeLocal(), FakeSDK(*replies)
        return HaikuClient(self.local, self.budget(**limits), self.sdk)

    def test_the_prompts_go_as_they_are_and_nothing_is_tuned(self):
        client = self.client(reply())
        client.chat([SYSTEM, USER], temperature=0)
        request = self.sdk.requests[0]
        self.assertEqual(request["system"], SYSTEM["content"])
        self.assertEqual(request["messages"], [USER])
        self.assertEqual(request["model"], MODEL)
        self.assertEqual(request["max_tokens"], MAX_TOKENS)
        for left_to_the_model in ("temperature", "top_p", "top_k", "seed", "thinking", "output_config"):
            self.assertNotIn(left_to_the_model, request)

    def test_the_text_is_read_by_type_because_thinking_comes_first(self):
        self.assertEqual(self.client(reply(thinking=True)).chat([USER]), "απάντηση")

    def test_real_usage_is_counted_after_every_call(self):
        client = self.client(reply(input_tokens=10_000, output_tokens=2_000), reply(input_tokens=10_000, output_tokens=2_000))
        client.chat([USER])
        self.assertAlmostEqual(client.budget.spent()[1], 0.002)
        client.chat([USER])
        self.assertAlmostEqual(client.budget.spent()[1], 0.004)
        self.assertEqual(client.last_chat["prompt_tokens"], 10_000)
        self.assertEqual(client.last_chat["answer_tokens"], 2_000)
        self.assertAlmostEqual(client.last_chat["cost"], 0.002)

    def test_no_call_is_made_once_it_could_pass_a_limit(self):
        client = self.client(reply(), run_limit=0.0005)
        with self.assertRaises(BudgetExceeded):
            client.chat([USER])
        self.assertEqual(self.sdk.requests, [])
        self.assertFalse(self.path.exists())

    def test_a_call_that_didnt_finish_stops_the_run_and_is_still_counted(self):
        for stop_reason in ("max_tokens", "refusal"):
            client = self.client(reply(stop_reason=stop_reason, input_tokens=1000, output_tokens=0))
            before = client.budget.spent()[1]
            with self.assertRaisesRegex(ModelError, stop_reason):
                client.chat([USER])
            self.assertGreater(client.budget.spent()[1], before)

    def test_the_judges_schema_goes_to_haiku_in_the_form_the_api_requires(self):
        schema = judge.schema(False)
        client = self.client(reply('{"chunks": []}'))
        client.chat([SYSTEM, USER], response_format=schema, temperature=0)
        sent = self.sdk.requests[0]["output_config"]["format"]
        self.assertEqual(sent["type"], "json_schema")
        self.assertIs(sent["schema"]["additionalProperties"], False)
        self.assertIs(sent["schema"]["properties"]["chunks"]["items"]["additionalProperties"], False)
        self.assertEqual(self.local.calls, [])
        self.assertNotIn("additionalProperties", schema, "the agent's own schema stays as it is")

    def test_the_enhancer_stays_local_and_costs_nothing(self):
        client = self.client()
        answer = client.chat([SYSTEM, USER], response_format=enhancer.SCHEMA, temperature=0)
        self.assertEqual(answer, '{"local": true}')
        self.assertEqual(self.sdk.requests, [])
        self.assertEqual(self.local.calls[0][2], {"temperature": 0})
        self.assertEqual(client.last_chat, self.local.last_chat)
        self.assertFalse(self.path.exists())

    def test_embeddings_stay_local(self):
        self.assertEqual(self.client().embed(["ερώτηση"], "model", 1), [[0.5]])
        self.assertEqual(self.sdk.requests, [])


class StrictSchema(unittest.TestCase):
    def test_every_object_and_nothing_else(self):
        schema = {"type": "object", "properties": {"type": {"type": "string"}, "list": {"type": "array", "items": {"type": "object", "properties": {}}}}}
        strict = strict_schema(schema)
        self.assertIs(strict["additionalProperties"], False)
        self.assertIs(strict["properties"]["list"]["items"]["additionalProperties"], False)
        self.assertNotIn("additionalProperties", strict["properties"]["type"])
        self.assertNotIn("additionalProperties", strict["properties"])


class TheKeyCheck(unittest.TestCase):
    def assert_clear(self, stop):
        self.assertIn("ANTHROPIC_API_KEY", str(stop.exception))
        self.assertNotIn("Ollama", str(stop.exception))

    def test_a_missing_key_stops_without_calling_anyone(self):
        with mock.patch.object(haiku_runs, "api_key", return_value=""), mock.patch.object(haiku_runs.anthropic, "Anthropic") as sdk:
            with self.assertRaises(SystemExit) as stop:
                check_key()
        self.assert_clear(stop)
        sdk.assert_not_called()

    def test_a_rejected_key_stops(self):
        for kind in (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
            sdk = FakeSDK()
            sdk.refuse_with = kind.__new__(kind)
            with self.assertRaises(SystemExit) as stop:
                check_key(sdk)
            self.assert_clear(stop)
            self.assertIn("rejected", str(stop.exception))

    def test_an_unreachable_api_stops_and_says_so(self):
        sdk = FakeSDK()
        sdk.refuse_with = anthropic.APIConnectionError(request=mock.Mock())
        with self.assertRaises(SystemExit) as stop:
            check_key(sdk)
        self.assert_clear(stop)

    def test_a_good_key_passes_and_spends_nothing(self):
        sdk = FakeSDK()
        check_key(sdk)
        self.assertEqual((sdk.key_checks, sdk.requests), (1, []))

    def test_only_haikus_failures_are_told_apart_from_ollamas(self):
        self.assertIn("ANTHROPIC_API_KEY", failure_text(ModelError(f"the call to {MODEL} failed: AuthenticationError: x")))
        self.assertIn("ANTHROPIC_API_KEY", failure_text(ModelError(f"{MODEL} stopped with refusal, so there is no complete answer to use")))
        self.assertIsNone(failure_text(ModelError("cannot reach Ollama at http://localhost:11434: refused")))


class TheMixedClient(WithLedger):
    def client(self, *replies):
        self.local, self.sdk = FakeLocal(), FakeSDK(*replies)
        return MixedClient(self.local, self.budget(), self.sdk)

    def test_the_judge_stays_local_at_its_local_settings_and_costs_nothing(self):
        client = self.client()
        answer = client.chat([SYSTEM, USER], response_format=judge.schema(False), temperature=0)
        self.assertEqual(answer, '{"local": true}')
        self.assertEqual(self.local.calls[0][2], {"temperature": 0})
        self.assertIn("decision", self.local.calls[0][1]["properties"])
        self.assertEqual(self.sdk.requests, [])
        self.assertEqual(client.last_chat, self.local.last_chat)
        self.assertFalse(self.path.exists())

    def test_the_enhancer_stays_local(self):
        client = self.client()
        client.chat([SYSTEM, USER], response_format=enhancer.SCHEMA, temperature=0)
        self.assertEqual(self.sdk.requests, [])
        self.assertEqual(len(self.local.calls), 1)

    def test_the_writer_goes_to_haiku_and_is_counted(self):
        client = self.client(reply(input_tokens=10_000, output_tokens=2_000))
        self.assertEqual(client.chat([SYSTEM, USER]), "απάντηση")
        self.assertEqual(self.local.calls, [])
        self.assertNotIn("output_config", self.sdk.requests[0])
        self.assertAlmostEqual(client.budget.spent()[1], 0.002)

    def test_each_system_gets_its_client(self):
        local, ledger = FakeLocal(), self.budget()
        with mock.patch.object(HaikuClient, "__init__", return_value=None):
            self.assertIs(type(client_for("agent-mixed", local, ledger)), MixedClient)
            self.assertIs(type(client_for("agent-haiku", local, ledger)), HaikuClient)
            self.assertIs(type(client_for("oneshot-haiku", local, ledger)), HaikuClient)


class ManualRuns(WithLedger):
    def run_one(self, who, body, sdk):
        output = io.StringIO()
        with mock.patch.object(haiku_runs, "MANUAL_LEDGER", self.path), mock.patch.object(haiku_runs.ModelClient, "from_settings", return_value=FakeLocal()), contextlib.redirect_stdout(output):
            with manual_run(who, sdk) as client:
                body(client)
        return output.getvalue()

    def test_they_have_their_own_gitignored_record_and_limit(self):
        self.assertEqual(MANUAL_LIMIT, 2.00)
        self.assertNotEqual(MANUAL_LEDGER, budget.LEDGER)
        self.assertEqual(subprocess.run(["git", "check-ignore", "-q", str(MANUAL_LEDGER)]).returncode, 0)
        self.assertNotEqual(subprocess.run(["git", "check-ignore", "-q", str(budget.LEDGER)]).returncode, 0)

    def test_what_it_prints_at_the_start_and_the_end(self):
        sdk = FakeSDK(reply(input_tokens=10_000, output_tokens=2_000))
        printed = self.run_one("Judge + Writer", lambda client: client.chat([USER]), sdk)
        self.assertTrue(printed.startswith("Judge + Writer: Claude Haiku (cloud). The question and chunks leave this machine.\n"))
        self.assertIn("This question cost $0.0020.", printed)
        self.assertIn("$0.0020 of $2.00", printed)

    def test_the_key_is_checked_before_anything_else(self):
        sdk = FakeSDK()
        sdk.refuse_with = anthropic.AuthenticationError.__new__(anthropic.AuthenticationError)
        body = mock.Mock()
        with self.assertRaises(SystemExit) as stop:
            self.run_one("Writer", body, sdk)
        self.assertIn("ANTHROPIC_API_KEY", str(stop.exception))
        body.assert_not_called()

    def test_a_second_question_counts_on_top_of_the_first_but_prints_its_own_cost(self):
        self.run_one("Writer", lambda client: client.chat([USER]), FakeSDK(reply(input_tokens=10_000, output_tokens=2_000)))
        printed = self.run_one("Writer", lambda client: client.chat([USER]), FakeSDK(reply(input_tokens=5_000, output_tokens=1_000)))
        self.assertIn("This question cost $0.0010.", printed)
        self.assertIn("$0.0030 of $2.00", printed)

    def test_the_limit_stops_cleanly(self):
        Budget("manual", self.path).add(1.999, 1, 1)
        with self.assertRaises(SystemExit) as stop:
            self.run_one("Writer", lambda client: client.chat([USER]), FakeSDK(reply()))
        self.assertIn("budget guard", str(stop.exception))

    def test_a_haiku_failure_never_mentions_ollama(self):
        sdk = FakeSDK(reply(stop_reason="refusal"))
        with self.assertRaises(SystemExit) as stop:
            self.run_one("Writer", lambda client: client.chat([USER]), sdk)
        self.assertNotIn("Ollama", str(stop.exception))
        self.assertIn(MODEL, str(stop.exception))

    def test_a_local_failure_is_left_to_friendly_errors(self):
        def fail(client):
            raise ModelError("cannot reach Ollama at http://localhost:11434: refused")
        with self.assertRaises(ModelError):
            self.run_one("Writer", fail, FakeSDK())


class TheFlag(unittest.TestCase):
    def test_ask_is_local_by_default(self):
        with mock.patch("sys.argv", ["ask", "ερώτηση"]), mock.patch.object(ask, "connect"), mock.patch.object(ask, "ask"), mock.patch.object(ask, "print_result"), \
                mock.patch.object(ask, "ModelClient") as local, mock.patch.object(haiku_runs, "manual_run") as cloud:
            ask.main()
        local.from_settings.assert_called_once()
        cloud.assert_not_called()

    def test_ask_with_the_flag_uses_haiku(self):
        with mock.patch("sys.argv", ["ask", "ερώτηση", "--haiku"]), mock.patch.object(ask, "connect"), mock.patch.object(ask, "ask") as answer, mock.patch.object(ask, "print_result"), \
                mock.patch.object(ask, "ModelClient") as local, mock.patch.object(haiku_runs, "manual_run") as cloud:
            ask.main()
        cloud.assert_called_once_with("Writer")
        local.from_settings.assert_not_called()
        self.assertIs(answer.call_args.args[1], cloud.return_value.__enter__.return_value)

    def test_agent_is_local_by_default(self):
        with mock.patch("sys.argv", ["agent", "ερώτηση"]), mock.patch.object(agent, "connect"), mock.patch.object(agent, "run"), mock.patch.object(agent, "print_result"), \
                mock.patch.object(agent, "ModelClient") as local, mock.patch.object(haiku_runs, "manual_run") as cloud:
            agent.main()
        local.from_settings.assert_called_once()
        cloud.assert_not_called()

    def test_agent_with_the_flag_uses_haiku_and_the_trace_still_prints(self):
        output = io.StringIO()
        with mock.patch("sys.argv", ["agent", "ερώτηση", "--haiku", "--trace"]), mock.patch.object(agent, "connect"), mock.patch.object(agent, "run") as run, mock.patch.object(agent, "print_result") as result, \
                mock.patch.object(agent, "trace_lines", return_value=["ROUND 1"]) as trace, mock.patch.object(agent, "ModelClient") as local, mock.patch.object(haiku_runs, "manual_run") as cloud, contextlib.redirect_stdout(output):
            agent.main()
        cloud.assert_called_once_with("Judge + Writer")
        local.from_settings.assert_not_called()
        self.assertIs(run.call_args.args[1], cloud.return_value.__enter__.return_value)
        trace.assert_called_once()
        result.assert_called_once()
        self.assertIn("ROUND 1", output.getvalue())


class EvaluateWithHaiku(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.results = Path(folder.name)

    def args(self, **changes):
        return argparse.Namespace(**{"split": "dev", "system": "agent-mixed", "fusion": "semantic", "number_rule": "units", "enhancer": None, "max_per_document": 2,
                                     "embedding": "qwen3-4b", "retrieval_only": False, "name": "try", "ids": "x", "reuse_enhancer": None, **changes})

    def run_with(self, answer):
        """One question, with the database and models replaced, and the key check passed."""
        item = {"id": "x"}
        with mock.patch.object(evaluate, "RESULTS", self.results), mock.patch.object(haiku_runs, "check_key"), mock.patch.object(evaluate, "load_questions", return_value=[item]), \
                mock.patch.object(evaluate, "connect"), mock.patch.object(evaluate.ModelClient, "from_settings", return_value=FakeLocal()), mock.patch.object(haiku_runs, "client_for"), \
                mock.patch.dict(evaluate.SYSTEMS, {"agent-mixed": answer}), mock.patch.object(evaluate.Budget, "spent", return_value=(0.0, 0.0)), contextlib.redirect_stdout(io.StringIO()):
            evaluate.run(self.args())

    def test_a_missing_key_stops_before_any_search_and_leaves_no_folder(self):
        with mock.patch.object(evaluate, "RESULTS", self.results), mock.patch.object(haiku_runs, "api_key", return_value=""), mock.patch.object(evaluate, "connect") as database:
            with self.assertRaises(SystemExit) as stop:
                evaluate.run(self.args())
        self.assertIn("ANTHROPIC_API_KEY", str(stop.exception))
        self.assertNotIn("Ollama", str(stop.exception))
        database.assert_not_called()
        self.assertEqual(list(self.results.iterdir()), [])

    def test_a_missing_key_claims_no_test_run(self):
        with mock.patch.object(evaluate, "RESULTS", self.results), mock.patch.object(haiku_runs, "api_key", return_value=""), mock.patch.object(evaluate, "frozen_refusal", return_value=None), \
                mock.patch.object(evaluate, "dev_run_finished", return_value=True), mock.patch.object(evaluate, "claim_test_run") as claim:
            with self.assertRaises(SystemExit):
                evaluate.run(self.args(split="test", system="agent-haiku", ids=None, max_per_document=4))
        claim.assert_not_called()

    def test_a_haiku_failure_on_the_first_question_leaves_no_folder_and_no_ollama(self):
        def fail(*_):
            raise ModelError(f"the call to {MODEL} failed: AuthenticationError: rejected")
        with self.assertRaises(SystemExit) as stop:
            self.run_with(fail)
        self.assertIn("ANTHROPIC_API_KEY", str(stop.exception))
        self.assertNotIn("Ollama", str(stop.exception))
        self.assertEqual(list(self.results.iterdir()), [])

    def test_a_local_failure_stays_a_local_failure(self):
        def fail(*_):
            raise ModelError("cannot reach Ollama at http://localhost:11434: refused")
        with self.assertRaises(ModelError):
            self.run_with(fail)
        self.assertEqual(list(self.results.iterdir()), [])

    def test_a_budget_stop_on_the_first_question_leaves_no_folder(self):
        def fail(*_):
            raise BudgetExceeded("over the limit")
        with self.assertRaisesRegex(SystemExit, "budget guard"):
            self.run_with(fail)
        self.assertEqual(list(self.results.iterdir()), [])

    def test_the_folder_comes_with_the_first_answer(self):
        record = {"id": "x", "category": "single_source", "retrieval": None, "times": {"step": 1.0}}
        self.run_with(lambda *_: record)
        run = next(self.results.iterdir())
        self.assertTrue((run / "items.jsonl").exists() and (run / "summary.json").exists())
        self.assertEqual(json.loads((run / "summary.json").read_text(encoding="utf-8"))["config"]["judge"], "local")


if __name__ == "__main__":
    unittest.main()
