"""Tracing with OpenTelemetry: one trace per question, a span per step, sent over OTLP to Jaeger and Phoenix in the same run.

Only labour_rag.traced loads this file, and only when TRACING is on. It wraps the frozen code from the outside, at run time: the model
client, the agent's graph nodes and a few functions. No frozen file knows about it. See docs/observability.md.

Attribute names: gen_ai.* are OpenTelemetry's standard ones, input.value, llm.*, retrieval.* and openinference.* are what Phoenix reads
to recognise LLM and retrieval spans, and labour.* are our own. The names are plain strings, so no extra package is needed for them.
"""

import json
import logging
import os
import socket
import sys
import time
from functools import wraps
from urllib.parse import urlsplit

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode

from . import ask as ask_module
from . import citations, enhancer
from .retrieve import POOL

SERVICE = "labour-law-rag"
# Where each viewer takes traces, over OTLP. Vendor-neutral: both get the same spans from the same exporter code.
VIEWERS = {"Jaeger": "http://127.0.0.1:4318/v1/traces", "Phoenix": "http://127.0.0.1:6006/v1/traces"}
JAEGER_TRACE = "http://127.0.0.1:16686/trace/{}"
PHOENIX_PAGE = "http://127.0.0.1:6006"
START_VIEWERS = "docker compose --profile observability up -d"
EXPORT_TIMEOUT = 3      # seconds per try, so that a viewer that goes away can't hold up the end of a command
SYSTEMS = {"ModelClient": "local", "HaikuClient": "haiku", "MixedClient": "mixed"}


def running(endpoint):
    """True if something answers at this address. A quick look, so that a missing viewer costs one warning and no waiting."""
    parts = urlsplit(endpoint)
    try:
        with socket.create_connection((parts.hostname, parts.port), timeout=0.3):
            return True
    except OSError:
        return False


class ViewerExporter(SpanExporter):
    """An OTLP exporter that never lets a viewer's failure reach the question: it warns once and carries on."""

    def __init__(self, name, inner, warn):
        self.name, self.inner, self.warn, self.failed = name, inner, warn, False

    def export(self, spans):
        try:
            result = self.inner.export(spans)
        except Exception:
            result = SpanExportResult.FAILURE
        if result is not SpanExportResult.SUCCESS:
            self.failed = True
            self.warn(f"Tracing is on, but {self.name} didn't take the trace, so it isn't there. The question was still answered.")
        return result

    def shutdown(self):
        self.inner.shutdown()

    def force_flush(self, timeout_millis=30000):
        return self.inner.force_flush(timeout_millis)


def quiet(annotate):
    """Writing down what happened must never change what happens: a mistake here costs a warning, not the question."""

    @wraps(annotate)
    def safe(self, *args, **kwargs):
        try:
            annotate(self, *args, **kwargs)
        except Exception as error:
            self.warn(f"Tracing couldn't record part of a span ({type(error).__name__}).")
    return safe


class Tracing:
    def __init__(self, exporters=()):
        # Our own provider, not the global one: the Anthropic SDK and LangGraph look for the global one, so they stay silent and
        # every span in a trace is one we wrote.
        self.provider = TracerProvider(resource=Resource.create({"service.name": SERVICE, "openinference.project.name": SERVICE}))
        for exporter in exporters:
            self.provider.add_span_processor(BatchSpanProcessor(exporter))
        self.tracer = self.provider.get_tracer("labour_rag")
        self.active = None          # the question being answered: one at a time
        self.run_name = None        # the evaluate run, to filter by
        self.trace_ids = []
        self.warned = False
        self.saved = []

    def warn(self, message):
        """One warning per command, on stderr, so that the answer on stdout stays as it was."""
        if not self.warned:
            self.warned = True
            print(message, file=sys.stderr, flush=True)

    def patch(self, owner, name, value):
        self.saved.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    def finish(self):
        """Put everything back and send what's left. Called at the end of a command."""
        for owner, name, value in reversed(self.saved):
            setattr(owner, name, value)
        self.saved = []
        self.provider.shutdown()

    # One question

    def question(self, question, client, kind):
        """A context manager for one question's root span, with the client wrapped so that every model call is seen."""
        tracing = self

        class Scope:
            def __enter__(self):
                self.manager = tracing.tracer.start_as_current_span("question")
                root = self.manager.__enter__()
                tracing.trace_ids.append(format(root.get_span_context().trace_id, "032x"))
                tracing.active = {"root": root, "round": None, "cost": 0.0, "started": time.perf_counter()}
                system = SYSTEMS.get(type(client).__name__, "local")
                tracing.describe_question(root, question, system, kind)
                return root, TracedClient(client, tracing)

            def __exit__(self, *failure):
                try:
                    return self.manager.__exit__(*failure)
                finally:
                    tracing.active = None
        return Scope()

    @quiet
    def describe_question(self, root, question, system, kind):
        root.set_attribute("openinference.span.kind", kind)
        root.set_attribute("input.value", question)
        root.set_attribute("labour.question", question)
        root.set_attribute("labour.system", system)
        root.set_attribute("gen_ai.operation.name", "invoke_agent" if kind == "AGENT" else "chat")
        tags = [system] + ([self.run_name] if self.run_name else [])
        root.set_attribute("tag.tags", tags)
        root.set_attribute("metadata", json.dumps({"system": system, **({"run": self.run_name} if self.run_name else {})}))
        if self.run_name:
            root.set_attribute("labour.run_name", self.run_name)
            root.set_attribute("session.id", self.run_name)

    @quiet
    def conclude(self, root, answer, decision, rounds=None):
        root.set_attribute("output.value", answer)
        root.set_attribute("labour.decision", decision)
        root.set_attribute("labour.total_seconds", round(time.perf_counter() - self.active["started"], 3))
        root.set_attribute("labour.total_cost_usd", round(self.active["cost"], 8))
        if rounds is not None:
            root.set_attribute("labour.rounds", rounds)

    def record_failure(self, question, system, message):
        """A question that stopped before it began, such as a rejected key: still a trace, with the message on it."""
        with self.tracer.start_as_current_span("question") as root:
            self.trace_ids.append(format(root.get_span_context().trace_id, "032x"))
            root.set_attribute("openinference.span.kind", "CHAIN")
            root.set_attribute("input.value", question)
            root.set_attribute("labour.question", question)
            root.set_attribute("labour.system", system)
            root.set_attribute("labour.decision", "stopped")
            root.set_status(Status(StatusCode.ERROR, message))

    # What each step writes down

    @quiet
    def describe_model_call(self, span, step, inner, messages, answer):
        last = inner.last_chat
        local = getattr(inner, "local", None) or inner
        model = last.get("model") or getattr(local, "chat_model", None) or "unknown"
        provider = "anthropic" if model.startswith("claude") else "ollama"
        prompt, completion = last.get("prompt_tokens", 0), last.get("answer_tokens", 0)
        cost = last.get("cost") or 0.0
        self.active["cost"] += cost
        span.set_attributes({"labour.step": step, "labour.cost_usd": cost, "openinference.span.kind": "LLM",
                             # The standard GenAI names
                             "gen_ai.operation.name": "chat", "gen_ai.provider.name": provider, "gen_ai.request.model": model, "gen_ai.response.model": model,
                             "gen_ai.usage.input_tokens": prompt, "gen_ai.usage.output_tokens": completion,
                             # What Phoenix reads
                             "llm.model_name": model, "llm.provider": provider, "llm.token_count.prompt": prompt, "llm.token_count.completion": completion,
                             "llm.token_count.total": prompt + completion, "llm.cost.total": cost, "output.value": answer,
                             "llm.output_messages.0.message.role": "assistant", "llm.output_messages.0.message.content": answer})
        if last.get("done_reason"):
            span.set_attribute("gen_ai.response.finish_reasons", [str(last["done_reason"])])
        if last.get("thinking_tokens") is not None:
            span.set_attribute("gen_ai.usage.reasoning.output_tokens", last["thinking_tokens"])
        for i, message in enumerate(messages):
            span.set_attribute(f"llm.input_messages.{i}.message.role", message["role"])
            span.set_attribute(f"llm.input_messages.{i}.message.content", message["content"])
        users = [m["content"] for m in messages if m["role"] == "user"]
        if users:
            span.set_attribute("input.value", users[-1])

    @quiet
    def describe_search(self, span, query, method, candidates, kept, removed):
        span.set_attributes({"openinference.span.kind": "RETRIEVER", "labour.step": "search", "input.value": query, "labour.search.method": method,
                             "labour.search.candidates": candidates, "labour.search.kept": len(kept), "labour.search.removed_as_repeats": removed["near_duplicate"],
                             "labour.search.removed_as_same_document": removed["same_document"],
                             "labour.search.chunks": [f"[{c.get('n')}] {c.get('citation')}, {c.get('article') or '-'}, rank {c.get('rank')}" for c in kept]})
        for i, chunk in enumerate(kept):
            prefix = f"retrieval.documents.{i}.document"
            span.set_attribute(f"{prefix}.id", str(chunk.get("id")))
            span.set_attribute(f"{prefix}.content", chunk.get("text") or "")
            span.set_attribute(f"{prefix}.metadata", json.dumps({"law": chunk.get("citation"), "article": chunk.get("article"), "rank": chunk.get("rank"), "source": chunk.get("source")}, ensure_ascii=False))
            if isinstance(chunk.get("score"), (int, float)):
                span.set_attribute(f"{prefix}.score", float(chunk["score"]))

    @quiet
    def describe_judge(self, span, record, chunks):
        by_number = {c.get("n"): c for c in chunks}
        lines = []
        for v in record["verdicts"]:
            c = by_number.get(v["n"], {})
            only = f", only for {v['only_for']}" if v.get("only_for") else ""
            lines.append(f"[{v['n']}] {c.get('citation')}, {c.get('article') or '-'}: {v['relevance']}, applies {v['applies']}{only}. {v.get('reason') or ''}".strip())
        span.set_attributes({"labour.judge.decision": record["decision"], "labour.judge.missing": record.get("missing") or "", "labour.judge.stopped_by_code": bool(record.get("stopped_by_code")),
                             "labour.judge.verdicts": lines, "labour.judge.approved": list(record.get("approved") or []), "labour.judge.reply_was_readable": bool(record.get("judge_ok"))})

    @quiet
    def describe_round(self, span, number, record, went_on_to):
        """What the Judge said and what happened next: this is where to see why the agent searched again."""
        span.set_attributes({"openinference.span.kind": "CHAIN", "labour.round.number": number, "labour.round.judge_said": record["decision"], "labour.round.next_step": went_on_to,
                             "labour.round.missing": record.get("missing") or "", "labour.round.stopped_by_code": bool(record.get("stopped_by_code")),
                             "output.value": f"{record['decision']}" + (f": {record['missing']}" if record.get("missing") else "")})

    @quiet
    def describe_check(self, span, result):
        quotes = result["quotes"]
        span.set_attributes({"openinference.span.kind": "EVALUATOR", "labour.step": "citation check", "labour.check.quotes_found": sum(bool(q["found_in"]) for q in quotes),
                             "labour.check.quotes_total": len(quotes), "labour.check.citations": list(result["citations"]), "labour.check.ok": bool(result["ok"]),
                             "labour.check.refusal": bool(result["refusal"]), "labour.check.failures": list(result["failures"])})


class TracedClient:
    """The real client, with a span around each model call. It changes nothing: the arguments and the answer pass through as they are,
    and the Haiku client still recognises the Enhancer by its schema."""

    def __init__(self, inner, tracing):
        self.inner, self.tracing = inner, tracing

    def __getattr__(self, name):
        return getattr(self.inner, name)

    @property
    def last_chat(self):
        return self.inner.last_chat

    def chat(self, messages, response_format=None, **options):
        if self.tracing.active is None:
            return self.inner.chat(messages, response_format=response_format, **options)
        if response_format and response_format is not enhancer.SCHEMA:         # the Judge: its graph node already has the span
            span = trace.get_current_span()
            answer = self.inner.chat(messages, response_format=response_format, **options)
            self.tracing.describe_model_call(span, "judge", self.inner, messages, answer)
            return answer
        step = "enhancer" if response_format else "writer"
        with self.tracing.tracer.start_as_current_span(step) as span:
            answer = self.inner.chat(messages, response_format=response_format, **options)
            self.tracing.describe_model_call(span, step, self.inner, messages, answer)
            return answer


def _traced_check(tracing, real):
    @wraps(real)
    def check(*args, **kwargs):
        if tracing.active is None:
            return real(*args, **kwargs)
        with tracing.tracer.start_as_current_span("citation check") as span:
            result = real(*args, **kwargs)
            tracing.describe_check(span, result)
            return result
    return check


def _traced_ask(tracing, real):
    @wraps(real)
    def ask(conn, client, question, *args, **kwargs):
        with tracing.question(question, client, "CHAIN") as (root, traced):
            result = real(conn, traced, question, *args, **kwargs)
            tracing.conclude(root, result["answer"], "refused by the Writer" if result["check"]["refusal"] else "answered")
            return result
    return ask


def _traced_retrieve(tracing, real):
    @wraps(real)
    def retrieve(conn, client, question, *args, **kwargs):
        if tracing.active is None:
            return real(conn, client, question, *args, **kwargs)
        with tracing.tracer.start_as_current_span("search") as span:
            kept, removed, times = real(conn, client, question, *args, **kwargs)
            counts = {"near_duplicate": sum(r["reason"] == "near-duplicate" for r in removed), "same_document": sum(r["reason"] == "same document" for r in removed)}
            fusion = kwargs.get("fusion") or "semantic"
            tracing.describe_search(span, question, f"{fusion} search of the question", kwargs.get("pool", POOL), kept, counts)
            return kept, removed, times
    return retrieve


def instrument_ask(tracing):
    tracing.patch(ask_module, "ask", _traced_ask(tracing, ask_module.ask))
    tracing.patch(ask_module, "retrieve", _traced_retrieve(tracing, ask_module.retrieve))
    if not hasattr(citations.check, "__wrapped__"):
        tracing.patch(citations, "check", _traced_check(tracing, citations.check))


def instrument_agent(tracing):
    from . import agent        # LangGraph takes seconds to import, so only an agent run pays for it

    base = agent.StateGraph

    def wrap_node(name, action):
        @wraps(action)
        def node(state):
            return _run_node(tracing, name, action, state)
        return node

    class TracedStateGraph(base):
        def add_node(self, node, action=None, **kwargs):
            return super().add_node(node, wrap_node(node, action), **kwargs)

    real_run = agent.run

    @wraps(real_run)
    def run(conn, client, question, *args, **kwargs):
        with tracing.question(question, client, "AGENT") as (root, traced):
            result = real_run(conn, traced, question, *args, **kwargs)
            decision = "refused by the Judge" if result["refused_by_judge"] else "refused by the Writer" if result["check"]["refusal"] else "answered"
            tracing.conclude(root, result["answer"], decision, len(result["rounds"]))
            return result

    tracing.patch(agent, "StateGraph", TracedStateGraph)
    tracing.patch(agent, "run", run)
    if not hasattr(citations.check, "__wrapped__"):
        tracing.patch(citations, "check", _traced_check(tracing, citations.check))


def _end_round(tracing, failure=None):
    question = tracing.active
    if question and question["round"] is not None:
        if failure is not None:
            question["round"].set_status(Status(StatusCode.ERROR, f"{type(failure).__name__}: {failure}"))
        question["round"].end()
        question["round"] = None


def _run_node(tracing, name, action, state):
    """One step of the agent's graph, as it runs. Every node's result is the frozen code's own: this only reads it."""
    question = tracing.active
    if question is None or name in ("write", "refuse"):
        if question is None:
            return action(state)
        with trace.use_span(question["root"], end_on_exit=False):      # the writer and the citation check hang directly off the question
            return action(state)
    try:
        if name in ("search", "search_again"):
            number = state.get("round", 0) + 1
            question["round"] = tracing.tracer.start_span(f"round {number}", context=trace.set_span_in_context(question["root"]))
            question["number"] = number
            with tracing.tracer.start_as_current_span("search", context=trace.set_span_in_context(question["round"])) as span:
                update = action(state)
                current = update["current"]
                candidates = len(update["first"]["fused"]) if update.get("first") else len(current["chunks"]) + sum(current["removed"].values())
                tracing.describe_search(span, state["question"], "; ".join(current["searched"]), candidates, current["chunks"], current["removed"])
                return update
        if name == "judge":
            with tracing.tracer.start_as_current_span("judge", context=trace.set_span_in_context(question["round"])) as span:
                update = action(state)
                record = update["rounds"][-1]
                tracing.describe_judge(span, record, state["current"]["chunks"])
            tracing.describe_round(question["round"], question["number"], record, update["verdict"]["decision"])
            _end_round(tracing)
            return update
        return action(state)
    except Exception as failure:
        _end_round(tracing, failure)
        raise


def instrument(tracing, command, arguments):
    """Wrap what this command will use. evaluate is only read: the run's name comes from the folder it opens."""
    if command == "ask":
        instrument_ask(tracing)
    elif command == "agent":
        instrument_agent(tracing)
    else:
        from . import evaluate
        system = arguments[arguments.index("--system") + 1] if "--system" in arguments[:-1] else "one-shot"
        real_read = evaluate.read_records

        def read_records(run_dir):
            tracing.run_name = tracing.run_name or run_dir.name
            return real_read(run_dir)

        tracing.patch(evaluate, "read_records", read_records)
        if system in evaluate.AGENT_SYSTEMS:
            instrument_agent(tracing)
        else:
            instrument_ask(tracing)
            tracing.patch(evaluate, "ask", ask_module.ask)      # evaluate holds its own name for it


def start(viewers=VIEWERS):
    """Tracing with an exporter for each viewer that's running. With none, questions are still answered, and one warning says why."""
    # The SDK could send our trace id to Anthropic in a header. A trace stays on this machine.
    os.environ["ANTHROPIC_OPEN_TELEMETRY"] = "false"
    os.environ["ANTHROPIC_OPEN_TELEMETRY_PROPAGATION"] = "false"
    logging.getLogger("opentelemetry").setLevel(logging.CRITICAL)      # ViewerExporter gives the one warning instead
    missing = [name for name, endpoint in viewers.items() if not running(endpoint)]
    tracing = Tracing()
    tracing.exporters = {}
    for name, endpoint in viewers.items():
        if name not in missing:
            tracing.exporters[name] = ViewerExporter(name, OTLPSpanExporter(endpoint=endpoint, timeout=EXPORT_TIMEOUT), tracing.warn)
            tracing.provider.add_span_processor(BatchSpanProcessor(tracing.exporters[name]))
    if missing:
        tracing.warn(f"Tracing is on, but {' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} not running, so no trace goes there. Start the viewers with: {START_VIEWERS}")
    return tracing


def links(tracing):
    """Where to look, on stderr, so that the answer on stdout stays as it was."""
    if tracing.run_name:
        return [f"Traces of this run: {tracing.run_name}. In Jaeger, search by the attribute labour.run_name={tracing.run_name}. In Phoenix, filter by metadata['run'] == '{tracing.run_name}', or open its Sessions tab."]
    lines = []
    has = {name for name, exporter in getattr(tracing, "exporters", {}).items() if not exporter.failed}
    for trace_id in tracing.trace_ids:
        if "Jaeger" in has:
            lines.append(f"Trace in Jaeger: {JAEGER_TRACE.format(trace_id)}")
        if "Phoenix" in has:
            lines.append(f"Trace in Phoenix: {PHOENIX_PAGE}/redirects/traces/{trace_id}")
    return lines
