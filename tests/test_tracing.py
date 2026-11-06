"""Tracing, with an in-memory exporter in place of the viewers and the database and models replaced. Nothing here needs Docker or Ollama."""

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

import anthropic
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from labour_rag import agent, ask, citations, enhancer, evaluate, haiku_runs, search, traced, tracing
from labour_rag.budget import MODEL, Budget
from labour_rag.config import ROOT
from labour_rag.haiku_client import HaikuClient
from labour_rag.model_client import ModelError
from tests.test_agent import chunk, judged, verdict

QUESTION = "Η ερώτηση του ανθρώπου;"
VARIANTS = json.dumps({"rewritten": "ξαναγραμμένη", "variants": ["φράση α", "φράση β"], "law_refs": [], "topic_hint": "θέμα"}, ensure_ascii=False)


class ScriptedClient:
    """A local client, as far as the code can tell: the Judge's answers come from a script, with tokens to count."""
    chat_model = "ministral-3:8b"

    def __init__(self, *judge_answers, fail_on=None):
        self.judge_answers, self.fail_on, self.last_chat, self.calls = list(judge_answers), fail_on, {}, []

    def chat(self, messages, response_format=None, **options):
        step = "enhancer" if response_format is enhancer.SCHEMA else "judge" if response_format else "writer"
        self.calls.append(step)
        if step == self.fail_on:
            raise ModelError("cannot reach Ollama at http://localhost:11434: refused")
        self.last_chat = {"seconds": 1.0, "prompt_tokens": 100, "answer_tokens": 20, "load_seconds": 0.0, "done_reason": "stop"}
        return VARIANTS if step == "enhancer" else self.judge_answers.pop(0) if step == "judge" else "Η απάντηση από το 1980 [1]."


class TraceCase(unittest.TestCase):
    def setUp(self):
        self.exporter = InMemorySpanExporter()
        self.tracing = tracing.Tracing([self.exporter])
        self.addCleanup(self.tracing.finish)

    def spans(self):
        self.tracing.provider.force_flush()
        return self.exporter.get_finished_spans()

    def span(self, name, index=0):
        return [s for s in self.spans() if s.name == name][index]

    def parent_of(self, span):
        return next((s for s in self.spans() if span.parent and s.context.span_id == span.parent.span_id), None)

    def run_agent(self, client):
        lists = [[chunk(1), chunk(2)], [chunk(3), chunk(4)], [chunk(5), chunk(6)]]

        def multi_query(conn, client, queries, keyword_query="", k=10, embedding=None):
            found = lists.pop(0)
            return found, {"semantic": found, "keyword": []}

        with (mock.patch.object(search, "multi_query", multi_query), mock.patch.object(search, "keyword", lambda *a: []), mock.patch.object(search, "neighbours", lambda *a: []),
              mock.patch.object(agent, "law_in_data", lambda conn, law: True)):
            return agent.run(None, client, QUESTION)


class TheSwitch(unittest.TestCase):
    def env_file(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / ".env"
        path.write_text(text, encoding="utf-8")
        return path

    def test_off_when_nothing_says_otherwise(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("TRACING", None)
            self.assertFalse(traced.tracing_on(self.env_file("OTHER=1\n")))

    def test_on_in_the_file(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("TRACING", None)
            self.assertTrue(traced.tracing_on(self.env_file("TRACING=on\n")))
            self.assertFalse(traced.tracing_on(self.env_file("TRACING=off\n")))

    def test_the_environment_wins_over_the_file(self):
        with mock.patch.dict(os.environ, {"TRACING": "off"}):
            self.assertFalse(traced.tracing_on(self.env_file("TRACING=on\n")))

    def test_off_leaves_opentelemetrys_sdk_unloaded(self):
        code = ("import sys; from unittest import mock; from labour_rag import traced, ask\n"
                "sys.argv = ['traced', 'ask', '--help']\n"
                "with mock.patch.object(traced, 'tracing_on', return_value=False):\n"
                "    try: traced.main()\n"
                "    except SystemExit: pass\n"
                "print('opentelemetry.sdk' in sys.modules, 'labour_rag.tracing' in sys.modules)")
        done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, env={**os.environ, "TRACING": "off"})
        self.assertEqual(done.stdout.strip().splitlines()[-1], "False False", done.stderr)

    def test_the_plain_commands_never_load_tracing(self):
        for name in ("ask", "agent", "evaluate"):
            source = (ROOT / f"labour_rag/{name}.py").read_text(encoding="utf-8")
            self.assertNotRegex(source, r"(from|import) .*\b(tracing|traced)\b")

    def test_the_output_with_tracing_off_is_the_commands_own(self):
        def answer():
            print("ΑΠΑΝΤΗΣΗ")
        plain, wrapped = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(plain):
            answer()
        with mock.patch.object(ask, "main", answer), mock.patch.object(traced, "tracing_on", return_value=False), mock.patch("sys.argv", ["traced", "ask", "x"]), \
                contextlib.redirect_stdout(wrapped), contextlib.redirect_stderr(io.StringIO()):
            traced.main()
        self.assertEqual(wrapped.getvalue(), plain.getvalue())


class AgentTrace(TraceCase):
    def setUp(self):
        super().setUp()
        tracing.instrument_agent(self.tracing)

    def test_one_round_has_the_shape_the_brief_asks_for(self):
        self.run_agent(ScriptedClient(judged([verdict(1), verdict(2, "not_relevant")])))
        self.assertEqual({s.name for s in self.spans()}, {"question", "round 1", "search", "judge", "writer", "citation check"})
        self.assertEqual(self.parent_of(self.span("round 1")).name, "question")
        self.assertEqual(self.parent_of(self.span("search")).name, "round 1")
        self.assertEqual(self.parent_of(self.span("judge")).name, "round 1")
        self.assertEqual(self.parent_of(self.span("writer")).name, "question")
        self.assertEqual(self.parent_of(self.span("citation check")).name, "question")
        self.assertIsNone(self.span("question").parent)
        self.assertEqual(len({s.context.trace_id for s in self.spans()}), 1)

    def test_the_root_says_what_was_asked_and_what_came_of_it(self):
        self.run_agent(ScriptedClient(judged([verdict(1), verdict(2, "not_relevant")])))
        root = self.span("question").attributes
        self.assertEqual(root["labour.question"], QUESTION)
        self.assertEqual(root["input.value"], QUESTION)
        self.assertEqual(root["labour.system"], "local")
        self.assertEqual(root["labour.decision"], "answered")
        self.assertEqual(root["labour.rounds"], 1)
        self.assertGreaterEqual(root["labour.total_seconds"], 0)
        self.assertEqual(root["labour.total_cost_usd"], 0.0)
        self.assertIn("Η απάντηση", root["output.value"])

    def test_search_shows_its_chunks_as_retrieved_documents(self):
        self.run_agent(ScriptedClient(judged([verdict(1), verdict(2, "not_relevant")])))
        search_span = self.span("search").attributes
        self.assertEqual(search_span["openinference.span.kind"], "RETRIEVER")
        self.assertEqual(search_span["labour.search.kept"], 2)
        self.assertEqual(search_span["labour.search.method"], "the question")
        self.assertEqual(search_span["retrieval.documents.0.document.id"], "glc-00001-000")
        self.assertEqual(search_span["retrieval.documents.0.document.content"], chunk(1)["text"])
        metadata = json.loads(search_span["retrieval.documents.0.document.metadata"])
        self.assertEqual((metadata["law"], metadata["article"], metadata["rank"]), (chunk(1)["citation"], "Άρθρο 1", 1))

    def test_the_judge_shows_model_tokens_verdicts_and_decision(self):
        self.run_agent(ScriptedClient(judged([verdict(1), verdict(2, "not_relevant")])))
        judge = self.span("judge").attributes
        self.assertEqual(judge["openinference.span.kind"], "LLM")
        self.assertEqual(judge["gen_ai.request.model"], "ministral-3:8b")
        self.assertEqual(judge["gen_ai.provider.name"], "ollama")
        self.assertEqual((judge["gen_ai.usage.input_tokens"], judge["gen_ai.usage.output_tokens"]), (100, 20))
        self.assertEqual((judge["llm.token_count.prompt"], judge["llm.token_count.completion"], judge["llm.token_count.total"]), (100, 20, 120))
        self.assertEqual(judge["labour.judge.decision"], "answer")
        self.assertEqual(len(judge["labour.judge.verdicts"]), 2)
        self.assertIn("not_relevant", judge["labour.judge.verdicts"][1])
        self.assertEqual(judge["labour.judge.approved"], ("glc-00001-000",))

    def test_you_can_see_why_it_searched_again(self):
        self.run_agent(ScriptedClient(judged([verdict(1, "not_relevant"), verdict(2, "not_relevant")], "search_again", "λείπει το άρθρο"), judged([verdict(1), verdict(2)])))
        first, second = self.span("round 1").attributes, self.span("round 2").attributes
        self.assertEqual(first["labour.round.judge_said"], "search_again")
        self.assertEqual(first["labour.round.next_step"], "search_again")
        self.assertEqual(first["labour.round.missing"], "λείπει το άρθρο")
        self.assertEqual(second["labour.round.judge_said"], "answer")
        self.assertEqual(self.span("judge", 0).attributes["labour.judge.missing"], "λείπει το άρθρο")
        self.assertEqual(self.span("question").attributes["labour.rounds"], 2)

    def test_no_attribute_name_sits_inside_another(self):
        """Phoenix nests dotted names, so a value at labour.round would hide labour.round.judge_said."""
        self.run_agent(ScriptedClient(judged([verdict(1, "not_relevant"), verdict(2, "not_relevant")], "search_again", "λείπει"), judged([verdict(1), verdict(2)])))
        for span in self.spans():
            names = set(span.attributes)
            clashes = {a for a in names for b in names if b.startswith(a + ".")}
            self.assertEqual(clashes, set(), span.name)
        self.assertEqual(self.span("round 2").attributes["labour.round.number"], 2)

    def test_the_stop_rule_shows_when_the_code_overrules_the_judge(self):
        self.run_agent(ScriptedClient(judged([verdict(1), verdict(2)], "search_again", "κι άλλο")))
        first = self.span("round 1").attributes
        self.assertEqual(first["labour.round.judge_said"], "search_again")
        self.assertEqual(first["labour.round.next_step"], "answer")
        self.assertTrue(first["labour.round.stopped_by_code"])

    def test_the_enhancer_has_its_own_span_in_the_search_of_its_round(self):
        self.run_agent(ScriptedClient(judged([verdict(1, "not_relevant"), verdict(2, "not_relevant")], "search_again", "λείπει"), judged([verdict(1), verdict(2)])))
        spans = self.span("enhancer")
        self.assertEqual(self.parent_of(spans).name, "search")
        self.assertEqual(self.parent_of(self.parent_of(spans)).name, "round 2")
        self.assertEqual(spans.attributes["openinference.span.kind"], "LLM")

    def test_the_writer_shows_its_model_and_answer(self):
        self.run_agent(ScriptedClient(judged([verdict(1), verdict(2, "not_relevant")])))
        writer = self.span("writer").attributes
        self.assertEqual(writer["gen_ai.response.model"], "ministral-3:8b")
        self.assertEqual(writer["output.value"], "Η απάντηση από το 1980 [1].")
        self.assertEqual(writer["llm.output_messages.0.message.content"], "Η απάντηση από το 1980 [1].")
        self.assertEqual(writer["llm.input_messages.0.message.role"], "system")

    def test_the_citation_check_counts_quotes_found(self):
        self.run_agent(ScriptedClient(judged([verdict(1), verdict(2, "not_relevant")])))
        check = self.span("citation check").attributes
        self.assertEqual((check["labour.check.quotes_found"], check["labour.check.quotes_total"]), (0, 0))
        self.assertTrue(check["labour.check.ok"])

    def test_a_refusal_has_no_writer_and_says_so(self):
        self.run_agent(ScriptedClient(judged([verdict(1, "not_relevant"), verdict(2, "not_relevant")], "refuse")))
        self.assertNotIn("writer", {s.name for s in self.spans()})
        self.assertEqual(self.span("question").attributes["labour.decision"], "refused by the Judge")

    def test_the_answer_is_the_same_as_without_tracing(self):
        script = [judged([verdict(1, "not_relevant"), verdict(2, "not_relevant")], "search_again", "λείπει"), judged([verdict(1), verdict(2)])]
        traced_result = self.run_agent(ScriptedClient(*script))
        self.tracing.finish()
        plain_result = self.run_agent(ScriptedClient(*script))
        for key in ("answer", "check", "chunks", "laws_found", "laws_missing", "refused_by_judge", "tokens"):
            self.assertEqual(traced_result[key], plain_result[key], key)
        self.assertEqual([r["decision"] for r in traced_result["rounds"]], [r["decision"] for r in plain_result["rounds"]])

    def test_finish_puts_everything_back(self):
        self.assertTrue(hasattr(agent.run, "__wrapped__"))
        self.tracing.finish()
        self.assertFalse(hasattr(agent.run, "__wrapped__"))
        self.assertFalse(hasattr(citations.check, "__wrapped__"))
        self.assertEqual(agent.StateGraph.__name__, "StateGraph")


class Costs(TraceCase):
    """With the real Haiku client around a stand-in for Anthropic's package, so the real cost reaches the trace."""

    def setUp(self):
        super().setUp()
        tracing.instrument_agent(self.tracing)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.ledger = Path(folder.name) / "spend.json"

    def client(self, *judge_answers):
        from types import SimpleNamespace
        answers = list(judge_answers)

        def create(**request):
            text = answers.pop(0) if "output_config" in request else "Η απάντηση από το 1980 [1]."
            usage = SimpleNamespace(input_tokens=10_000, output_tokens=2_000, cache_creation_input_tokens=None, cache_read_input_tokens=None, output_tokens_details=SimpleNamespace(thinking_tokens=1_500))
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], usage=usage, stop_reason="end_turn", model=MODEL)

        return HaikuClient(ScriptedClient(), Budget("manual", self.ledger), SimpleNamespace(messages=SimpleNamespace(create=create)))

    def test_cost_tokens_and_model_reach_each_span_and_the_total(self):
        self.run_agent(self.client(judged([verdict(1), verdict(2, "not_relevant")])))
        judge, writer, root = self.span("judge").attributes, self.span("writer").attributes, self.span("question").attributes
        for span in (judge, writer):
            self.assertEqual(span["gen_ai.provider.name"], "anthropic")
            self.assertEqual(span["gen_ai.request.model"], MODEL)
            self.assertAlmostEqual(span["labour.cost_usd"], 0.002)
            self.assertEqual(span["gen_ai.usage.reasoning.output_tokens"], 1_500)
        self.assertEqual(root["labour.system"], "haiku")
        self.assertAlmostEqual(root["labour.total_cost_usd"], 0.004)

    def test_the_mixed_client_is_labelled_mixed_and_its_judge_local(self):
        base = self.client()
        mixed = haiku_runs.MixedClient(ScriptedClient(judged([verdict(1), verdict(2, "not_relevant")])), base.budget, base.sdk)
        self.run_agent(mixed)
        self.assertEqual(self.span("question").attributes["labour.system"], "mixed")
        self.assertEqual(self.span("judge").attributes["gen_ai.provider.name"], "ollama")
        self.assertEqual(self.span("writer").attributes["gen_ai.provider.name"], "anthropic")
        self.assertAlmostEqual(self.span("question").attributes["labour.total_cost_usd"], 0.002)


class AskTrace(TraceCase):
    def run_it(self, client):
        kept = [dict(chunk(1), n=1), dict(chunk(2), n=2)]
        removed = [dict(chunk(3), reason="near-duplicate", of="x")]
        with mock.patch.object(ask, "retrieve", lambda *a, **k: (kept, removed, {"search": 0.1})):
            tracing.instrument_ask(self.tracing)
            return ask.ask(None, client, QUESTION, fusion="semantic")

    def test_the_one_shot_has_search_writer_and_check_and_no_rounds(self):
        result = self.run_it(ScriptedClient())
        self.assertEqual({s.name for s in self.spans()}, {"question", "search", "writer", "citation check"})
        self.assertEqual(self.parent_of(self.span("search")).name, "question")
        search_span = self.span("search").attributes
        self.assertEqual(search_span["labour.search.method"], "semantic search of the question")
        self.assertEqual(search_span["labour.search.candidates"], 30)
        self.assertEqual(search_span["labour.search.removed_as_repeats"], 1)
        self.assertEqual(search_span["retrieval.documents.1.document.id"], "glc-00002-000")
        self.assertEqual(self.span("question").attributes["labour.decision"], "answered")
        self.assertIn("Η απάντηση", result["answer"])


class Failures(TraceCase):
    def test_ollama_down_is_an_error_on_the_step_and_the_question(self):
        tracing.instrument_agent(self.tracing)
        with self.assertRaises(ModelError):
            self.run_agent(ScriptedClient(judged([verdict(1), verdict(2)]), fail_on="writer"))
        for name in ("writer", "question"):
            status = self.span(name).status
            self.assertEqual(status.status_code, StatusCode.ERROR, name)
            self.assertIn("cannot reach Ollama", status.description)

    def test_an_error_in_the_judge_also_closes_its_round_with_the_message(self):
        tracing.instrument_agent(self.tracing)
        with self.assertRaises(ModelError):
            self.run_agent(ScriptedClient(fail_on="judge"))
        for name in ("judge", "round 1", "question"):
            self.assertEqual(self.span(name).status.status_code, StatusCode.ERROR, name)
            self.assertIn("cannot reach Ollama", self.span(name).status.description)

    def test_a_rejected_key_is_a_trace_with_the_message(self):
        self.tracing.record_failure(QUESTION, "haiku", "Anthropic's API rejected ANTHROPIC_API_KEY. Check the key in .env.")
        root = self.span("question")
        self.assertEqual(root.status.status_code, StatusCode.ERROR)
        self.assertIn("rejected ANTHROPIC_API_KEY", root.status.description)
        self.assertEqual(root.attributes["labour.system"], "haiku")

    def test_the_whole_command_records_a_rejected_key_and_still_stops_with_its_message(self):
        def rejected():
            raise SystemExit("Anthropic's API rejected ANTHROPIC_API_KEY.")
        with mock.patch.object(traced, "tracing_on", return_value=True), mock.patch.object(tracing, "start", return_value=self.tracing), mock.patch.object(tracing, "instrument"), \
                mock.patch.object(ask, "main", rejected), mock.patch("sys.argv", ["traced", "ask", QUESTION, "--haiku"]), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "rejected"):
                traced.main()
        self.assertEqual(self.exporter.get_finished_spans()[0].status.status_code, StatusCode.ERROR)

    def test_a_mistake_in_tracing_never_costs_the_question(self):
        tracing.instrument_agent(self.tracing)

        @tracing.quiet
        def broken(tracer, *args):
            raise KeyError("a step without the field we expected")

        stderr = io.StringIO()
        with mock.patch.object(tracing.Tracing, "describe_search", broken), mock.patch.object(tracing.Tracing, "describe_judge", broken), contextlib.redirect_stderr(stderr):
            result = self.run_agent(ScriptedClient(judged([verdict(1), verdict(2, "not_relevant")])))
        self.assertIn("Η απάντηση", result["answer"])
        self.assertEqual(len(stderr.getvalue().strip().splitlines()), 1)
        self.assertIn("couldn't record", stderr.getvalue())

    def test_quiet_turns_a_mistake_into_one_warning(self):
        class Broken:
            warnings = []

            def warn(self, message):
                self.warnings.append(message)

            @tracing.quiet
            def describe(self):
                raise KeyError("x")

        Broken().describe()
        self.assertEqual(len(Broken.warnings), 1)


class Viewers(unittest.TestCase):
    def test_with_no_viewer_running_there_is_one_warning_and_no_crash(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            t = tracing.start({"Jaeger": "http://127.0.0.1:9/v1/traces", "Phoenix": "http://127.0.0.1:9/v1/traces"})
            with t.tracer.start_as_current_span("question"):
                pass
            t.finish()
        lines = stderr.getvalue().strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("Jaeger and Phoenix are not running", lines[0])
        self.assertIn("--profile observability", lines[0])

    def test_one_viewer_down_is_named_and_the_other_still_gets_the_trace(self):
        server = self.collector()
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            t = tracing.start({"Jaeger": f"http://127.0.0.1:{server.server_port}/v1/traces", "Phoenix": "http://127.0.0.1:9/v1/traces"})
            with t.tracer.start_as_current_span("question"):
                pass
            t.finish()
        self.assertIn("Phoenix is not running", stderr.getvalue())
        self.assertEqual(server.paths, ["/v1/traces"])

    def test_both_viewers_get_the_same_trace_in_the_same_run(self):
        first, second = self.collector(), self.collector()
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            t = tracing.start({"Jaeger": f"http://127.0.0.1:{first.server_port}/v1/traces", "Phoenix": f"http://127.0.0.1:{second.server_port}/v1/traces"})
            with t.tracer.start_as_current_span("question"):
                pass
            t.finish()
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(first.paths, ["/v1/traces"])
        self.assertEqual(second.paths, ["/v1/traces"])
        self.assertEqual(first.bodies, second.bodies)

    def test_a_viewer_that_goes_away_mid_run_costs_one_warning(self):
        warnings = []

        class Gone:
            def export(self, spans):
                raise ConnectionError("gone")

        exporter = tracing.ViewerExporter("Jaeger", Gone(), warnings.append)
        self.assertEqual(exporter.export([]), SpanExportResult.FAILURE)
        self.assertIn("Jaeger", warnings[0])
        self.assertTrue(exporter.failed)

    def test_a_viewer_that_refused_gets_no_link(self):
        t = tracing.Tracing()
        t.trace_ids = ["abc"]
        t.exporters = {"Jaeger": tracing.ViewerExporter("Jaeger", None, print), "Phoenix": tracing.ViewerExporter("Phoenix", None, print)}
        t.exporters["Phoenix"].failed = True
        lines = tracing.links(t)
        self.assertEqual(len(lines), 1)
        self.assertIn("Jaeger", lines[0])
        t.provider.shutdown()

    def collector(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.server.paths.append(self.path)
                self.server.bodies.append(self.rfile.read(int(self.headers.get("content-length", 0))))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        server.paths, server.bodies = [], []
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server


class Safety(TraceCase):
    FAKE_KEY = "sk-ant-this-is-not-a-real-key-0123456789"

    def everything_recorded(self):
        return json.dumps([{"name": s.name, "attributes": {k: list(v) if isinstance(v, tuple) else v for k, v in s.attributes.items()}, "events": [str(e.attributes) for e in s.events],
                            "status": s.status.description, "resource": dict(s.resource.attributes)} for s in self.spans()], ensure_ascii=False)

    def test_the_key_and_env_contents_stay_out_of_every_span(self):
        tracing.instrument_agent(self.tracing)
        secrets = {"ANTHROPIC_API_KEY": self.FAKE_KEY, "POSTGRES_PASSWORD": "not-a-real-password-987"}
        with mock.patch.dict(os.environ, secrets):
            self.run_agent(ScriptedClient(judged([verdict(1), verdict(2, "not_relevant")])))
        recorded = self.everything_recorded()
        for secret in secrets.values():
            self.assertNotIn(secret, recorded)
        self.assertNotIn("ANTHROPIC_API_KEY", recorded)
        self.assertNotIn("POSTGRES_PASSWORD", recorded)

    def test_no_trace_id_goes_to_anthropic(self):
        seen = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                seen.update({k.lower(): v for k, v in self.headers.items()})
                self.rfile.read(int(self.headers.get("content-length", 0)))
                body = json.dumps({"id": "m", "type": "message", "role": "assistant", "model": MODEL, "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}}).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        before = {k: os.environ.get(k) for k in ("ANTHROPIC_OPEN_TELEMETRY", "ANTHROPIC_OPEN_TELEMETRY_PROPAGATION")}
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v) for k, v in before.items()])
        started = tracing.start({})
        client = anthropic.Anthropic(api_key="fake", base_url=f"http://127.0.0.1:{server.server_port}")
        with started.tracer.start_as_current_span("question"):
            client.messages.create(model=MODEL, max_tokens=1, messages=[{"role": "user", "content": "x"}])
        started.finish()
        self.assertTrue(seen)
        self.assertFalse({"traceparent", "tracestate", "baggage"} & seen.keys(), seen.keys())


class EvaluateRuns(TraceCase):
    def test_each_question_is_a_trace_tagged_with_the_run_name(self):
        with mock.patch.dict(sys.modules):
            tracing.instrument(self.tracing, "evaluate", ["--split", "dev", "--system", "agent"])
        with tempfile.TemporaryDirectory() as folder:
            evaluate.read_records(Path(folder) / "2026-11-06_my-run")
        for answer in (judged([verdict(1), verdict(2, "not_relevant")]), judged([verdict(1), verdict(2, "not_relevant")])):
            self.run_agent(ScriptedClient(answer))
        roots = [s for s in self.spans() if s.name == "question"]
        self.assertEqual(len(roots), 2)
        self.assertEqual(len({s.context.trace_id for s in roots}), 2)
        for root in roots:
            self.assertEqual(root.attributes["labour.run_name"], "2026-11-06_my-run")
            self.assertEqual(root.attributes["session.id"], "2026-11-06_my-run")
            self.assertEqual(json.loads(root.attributes["metadata"])["run"], "2026-11-06_my-run")
            self.assertIn("2026-11-06_my-run", root.attributes["tag.tags"])

    def test_a_one_shot_run_goes_through_evaluates_own_name_for_ask(self):
        real = evaluate.ask
        tracing.instrument(self.tracing, "evaluate", ["--split", "dev"])
        self.assertIsNot(evaluate.ask, real)
        self.tracing.finish()
        self.assertIs(evaluate.ask, real)


class TheViewersInCompose(unittest.TestCase):
    def setUp(self):
        self.compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    def service(self, name):
        return re.search(rf"^  {name}:\n(.*?)(?=^  \w+:\n|^\w|\Z)", self.compose, re.S | re.M).group(1)

    def test_they_only_start_when_asked(self):
        for name in ("jaeger", "phoenix"):
            self.assertIn("profiles: [observability]", self.service(name), name)
        self.assertNotIn("profiles", self.service("db"))

    def test_they_are_reachable_from_this_machine_only(self):
        for name in ("jaeger", "phoenix"):
            ports = re.findall(r'- "(.*?)"', self.service(name))
            self.assertTrue(ports, name)
            self.assertTrue(all(p.startswith("127.0.0.1:") for p in ports if ":" in p and "/" not in p and not p.startswith("phoenix")), ports)

    def test_their_versions_are_pinned(self):
        self.assertIn("image: jaegertracing/jaeger:2.22.0", self.service("jaeger"))
        self.assertIn("image: arizephoenix/phoenix:version-21.0.0-nonroot", self.service("phoenix"))

    def test_phoenix_sends_no_telemetry_of_its_own(self):
        self.assertIn('PHOENIX_TELEMETRY_ENABLED: "false"', self.service("phoenix"))

    def test_phoenix_takes_traces_without_a_login(self):
        self.assertIn('PHOENIX_ENABLE_AUTH: "false"', self.service("phoenix"))

    def test_no_restart_policy_brings_them_back_uninvited(self):
        for name in ("jaeger", "phoenix"):
            self.assertNotIn("restart:", self.service(name))


if __name__ == "__main__":
    unittest.main()
