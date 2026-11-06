"""The Haiku client and the budget guard, with a stand-in for the SDK: no test makes a real call or needs a key."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from labour_rag import enhancer, judge
from labour_rag.budget import LONG_RATES, RUN_LIMIT, SHORT_PROMPT, SHORT_RATES, TOTAL_LIMIT, Budget, BudgetExceeded, call_cost
from labour_rag.haiku_client import MAX_TOKENS, MODEL, HaikuClient, strict_schema
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


if __name__ == "__main__":
    unittest.main()
