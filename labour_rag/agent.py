"""The agent: search, let the Judge decide, search again if it asks, then write. A LangGraph graph.

    .venv/bin/python -m labour_rag.agent "Πόσες μέρες άδεια δικαιούμαι;" [--trace]

    search -> judge -> write -> END
                 |---> refuse -> END
                 '---> search again -> judge (at most MAX_ROUNDS rounds in all)

Round 1 searches the person's question. Round 2 reads further down that question's list, and adds the Query Enhancer's variants, the
laws the Judge named and the articles next to approved chunks. Round 3 replaces the further reading with what the Judge said was
missing. Searching stops as soon as the Judge has approved a chunk that answers directly. The writer sees only approved chunks and
the person's own question. When the Judge refuses, the code writes the refusal, so it can't invent anything; the writer may also
say it found nothing, as its prompt asks. docs/how-a-question-is-answered.md gives every rule in plain words.
"""

import argparse
import operator
import os
import textwrap
import time
from typing import Annotated, TypedDict

# LangSmith, LangChain's tracing service, comes along with LangGraph. It sends nothing unless a variable says "true" (see
# langsmith.utils.tracing_is_enabled), and these are read first, so one left in someone's shell can't switch it on.
os.environ["LANGSMITH_TRACING_V2"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from langgraph.graph import END, START, StateGraph  # noqa: E402

from . import citations, enhancer, judge, search  # noqa: E402
from .ask import closing_note, ensure_closing_note, system_prompt, user_message, NOTE_ADDED  # noqa: E402
from .db import connect, friendly_errors  # noqa: E402
from .embeddings import DEFAULT_EMBEDDING, EMBEDDINGS  # noqa: E402
from .law_mentions import find_mentions, law_name, law_references  # noqa: E402
from .model_client import ModelClient  # noqa: E402
from .normalize import normalize  # noqa: E402
from .retrieve import CONTEXT_CHUNKS, POOL, select  # noqa: E402

MAX_ROUNDS = 3
LIMIT = 4               # chunks per document in a search: more than one-shot's 2, because the Judge filters now
RANKED = 100            # how far the ranked lists are kept, for the scores in evaluate.py
NEW_CHUNKS = 8          # new chunks round 3 may show the Judge
ROUND_2_CHUNKS = 12     # and round 2, which also reads further down the plain question's list
PLAIN_PLACES = 8        # how far: the next places on that list that the Judge hasn't seen
LAW_PLACES = 2          # of those, for keyword search of a law the Judge named
NEIGHBOUR_PLACES = 2    # and for articles next to approved chunks
WRITER_CHUNKS = 8


class State(TypedDict, total=False):
    question: str
    round: int
    current: dict           # what this round searched and found, until the Judge has seen it
    rounds: Annotated[list, operator.add]
    first: dict             # round 1's ranked lists, for the scores
    verdict: dict
    approved: list
    judged: list            # ids the Judge has seen: they aren't searched for again
    variants: dict          # the enhancer's output
    laws_asked: list        # laws the question names
    laws_found: list        # laws the Judge named or the question names, and in our data
    laws_missing: list      # and not in our data
    laws_searched: list
    written: dict


def _with_article(law):
    """The preposition a law's name takes: στον Ν., στον Α.Ν., but στο Π.Δ., στο Ν.Δ."""
    return f"στον {law}" if law.startswith(("Ν. ", "Α.Ν.")) else f"στο {law}"


def missing_sentences(asked, missing):
    """What to tell the person about laws that aren't in our data."""
    lines = []
    for law in missing:
        if law in asked:
            lines.append(f"Το κείμενο του {law} δεν υπάρχει στα διαθέσιμα κείμενα.")
        else:
            lines.append(f"Τα αποσπάσματα παραπέμπουν {_with_article(law)}, αλλά το κείμενό του δεν υπάρχει στα διαθέσιμα κείμενα.")
    return lines


def refusal_text(asked, found, missing):
    """A clear refusal that names where the rule would be, when that's known."""
    lines = ["**Σύντομη απάντηση:** Δεν βρέθηκε απάντηση στα διαθέσιμα κείμενα."] + missing_sentences(asked, missing)
    lines += [f"Τα αποσπάσματα παραπέμπουν {_with_article(law)}." for law in found if law not in asked]
    return " ".join(lines)


def law_in_data(conn, law):
    """True if a law is a document in our data: same type and number, and a year at most 1 away, because a law may be voted one
    year and published the next. Texts mix up Ν., Ν.Δ. and Α.Ν., so those count as one type: telling someone a law is missing when
    it isn't is worse than the other way round."""
    mention = find_mentions(law, any_year=True)[0]
    laws = ["Ν.", "Ν.Δ.", "Α.Ν."]
    types = laws if mention.abbr in laws else [mention.abbr]
    return conn.execute("SELECT EXISTS (SELECT 1 FROM chunks WHERE act_abbr = ANY(%s) AND act_number = %s "
                        "AND (%s::int IS NULL OR abs(year - %s::int) <= 1))",
                        [types, mention.number, mention.year, mention.year]).fetchone()[0]


def sort_laws(conn, laws, state):
    """{laws_found, laws_missing} with these laws added, each looked up once."""
    found, missing = list(state.get("laws_found", [])), list(state.get("laws_missing", []))
    for law in laws:
        if law not in found and law not in missing:
            (found if law_in_data(conn, law) else missing).append(law)
    return {"laws_found": found, "laws_missing": missing}


def _labelled(chunks, source):
    return [{**c, "source": c.get("source") or source} for c in chunks]


def _summary(chunk):
    return {key: chunk.get(key) for key in ("n", "id", "doc_id", "citation", "article", "year", "source")}


def build_graph(conn, client, embedding=DEFAULT_EMBEDDING):
    """The graph, with its steps as functions that can reach the database and the models."""

    def first_search(state):
        started = time.perf_counter()
        question = state["question"]
        asked = law_references(normalize(question))
        fused, lists = search.multi_query(conn, client, [question], enhancer.law_keywords(asked), RANKED, embedding=embedding)
        kept, removed = select(fused[:POOL], CONTEXT_CHUNKS, LIMIT)
        chunks = [{**c, "source": "question" if c["semantic_rank"] else "keyword"} for c in kept]
        laws = [law_name(m) for m in find_mentions(normalize(question), any_year=True)]
        current = {"searched": ["the question"] + ([f"keyword: {enhancer.law_keywords(asked)}"] if asked else []), "chunks": chunks,
                   "removed": {"near_duplicate": sum(r["reason"] == "near-duplicate" for r in removed),
                               "same_document": sum(r["reason"] == "same document" for r in removed)},
                   "seconds": {"search": time.perf_counter() - started}}
        return {"round": 1, "current": current, "first": {"fused": fused, "lists": lists, "removed": removed}, "laws_asked": laws,
                "laws_searched": laws, **sort_laws(conn, laws, state)}

    def judge_chunks(state):
        started = time.perf_counter()
        current, number = state["current"], state["round"]
        chunks = current["chunks"]
        result = judge.judge(client, state["question"], chunks, number, MAX_ROUNDS)
        allowed = judge.approved(chunks, result)
        stopped = result["decision"] == "search_again" and judge.answers_directly(allowed, result)
        seconds = {**current["seconds"], "judge": time.perf_counter() - started}
        record = {"round": number, "searched": current["searched"], "chunks": [_summary(c) for c in chunks], "removed": current["removed"],
                  "verdicts": [{"n": n, **v} for n, v in result["verdicts"].items()], "decision": result["decision"], "stopped_by_code": stopped,
                  "missing": result["missing"], "laws_named": result["laws"], "laws_dropped": result["dropped_laws"],
                  "skipped_chunks": result["skipped"], "judge_ok": result["ok"], "approved": [c["id"] for c in allowed],
                  "tokens": result["tokens"], "raw": result["raw"], "seconds": {k: round(v, 2) for k, v in seconds.items()}}
        return {"verdict": {**result, "decision": "answer" if stopped else result["decision"]}, "approved": allowed,
                "judged": state.get("judged", []) + [c["id"] for c in chunks], "rounds": [record],
                **sort_laws(conn, result["laws"], state)}

    def next_step(state):
        decision, allowed, number = state["verdict"]["decision"], state["approved"], state["round"]
        if decision == "refuse":
            return "refuse"
        if decision == "answer" and allowed:
            return "write"
        if number < MAX_ROUNDS:
            return "search_again"       # asked to, or asked to answer with no chunk it approved
        return "write" if allowed else "refuse"

    def search_again(state):
        started = time.perf_counter()
        number, question, allowed = state["round"] + 1, state["question"], state["approved"]
        seen = set(state["judged"])
        seconds = {}

        output = state.get("variants")
        if output is None:
            enhancer_started = time.perf_counter()
            output = enhancer.enhance(client, question)
            seconds["enhancer"] = time.perf_counter() - enhancer_started
        queries = list(output["variants"])
        if number == MAX_ROUNDS and state["verdict"]["missing"]:
            queries.insert(0, state["verdict"]["missing"])
        searched = [f"variant: {v}" for v in output["variants"]]
        if number == MAX_ROUNDS and state["verdict"]["missing"]:
            searched.insert(0, f"what the Judge said was missing: {state['verdict']['missing']}")
        ranked, _ = search.multi_query(conn, client, queries, enhancer.law_keywords(output["law_refs"]), RANKED, embedding=embedding)

        new_laws = [law for law in state.get("laws_found", []) if law not in state.get("laws_searched", [])]
        by_law = []
        if new_laws:
            query = " ".join(new_laws)
            searched.append(f"keyword: {query}")
            by_law = [c for c in search.keyword(conn, query, search.CANDIDATES) if c["id"] not in seen][:LAW_PLACES]

        near = []
        for chunk in allowed:
            for neighbour in search.neighbours(conn, chunk["id"]):
                if neighbour["id"] not in seen and neighbour["id"] not in {n["id"] for n in near}:
                    near.append({**neighbour, "source": f"next to {chunk['id']}"})
        near = near[:NEIGHBOUR_PLACES]
        if near:
            searched.append("articles next to approved chunks: " + ", ".join(n["id"] for n in near))

        plain = []
        if number == 2:                 # chunks round 1 removed as repeats stay out: they repeat what the Judge has seen
            repeats = {r["id"] for r in state["first"]["removed"] if r["reason"] == "near-duplicate"}
            plain = [{**c, "source": f"question, rank {c['rank']}"} for c in state["first"]["fused"] if c["id"] not in seen | repeats][:PLAIN_PLACES]
        if plain:
            searched.insert(0, f"the question, further down its list: ranks {plain[0]['rank']} to {plain[-1]['rank']}")

        near_ids = {n["id"] for n in near}
        fresh = _labelled(by_law, "keyword") + [c for c in plain if c["id"] not in near_ids]
        taken = {c["id"] for c in fresh} | near_ids
        fresh += [c for c in _labelled(ranked, "variants") if c["id"] not in seen and c["id"] not in taken]
        room = len(allowed) + (ROUND_2_CHUNKS if number == 2 else NEW_CHUNKS) - len(near)
        kept, removed = select(allowed + fresh[:POOL], room, LIMIT)
        chunks = [{**c, "n": i} for i, c in enumerate(kept + near, 1)]       # neighbours pass the limit: they're the same document on purpose
        seconds["search"] = time.perf_counter() - started - seconds.get("enhancer", 0)
        current = {"searched": searched, "chunks": chunks,
                   "removed": {"near_duplicate": sum(r["reason"] == "near-duplicate" for r in removed),
                               "same_document": sum(r["reason"] == "same document" for r in removed)},
                   "seconds": seconds}
        return {"round": number, "current": current, "variants": output, "laws_searched": state.get("laws_searched", []) + new_laws}

    def write(state):
        chunks = [{**c, "n": i} for i, c in enumerate(state["approved"][:WRITER_CHUNKS], 1)]
        question = state["question"]
        started = time.perf_counter()
        raw = client.chat([{"role": "system", "content": system_prompt()}, {"role": "user", "content": user_message(question, chunks)}])
        seconds = {"model answer": time.perf_counter() - started}
        answer, note_added = ensure_closing_note(raw)
        lines = missing_sentences(state.get("laws_asked", []), state.get("laws_missing", []))
        note = closing_note()
        if lines:
            answer = answer.replace(note, " ".join(lines) + "\n\n" + note)
        started = time.perf_counter()
        check = citations.check(answer, chunks, note)
        seconds["citation check"] = time.perf_counter() - started
        if note_added:
            check["warnings"].append(NOTE_ADDED)
        return {"written": {"answer": answer, "raw_answer": raw, "chunks": chunks, "check": check, "seconds": seconds,
                            "tokens": dict(client.last_chat), "refused_by_judge": False}}

    def refuse(state):
        text = refusal_text(state.get("laws_asked", []), state.get("laws_found", []), state.get("laws_missing", []))
        answer = f"{text}\n\n{closing_note()}"
        return {"written": {"answer": answer, "raw_answer": text, "chunks": [], "check": citations.check(answer, [], closing_note()),
                            "seconds": {}, "tokens": {}, "refused_by_judge": True}}

    graph = StateGraph(State)
    graph.add_node("search", first_search)
    graph.add_node("judge", judge_chunks)
    graph.add_node("search_again", search_again)
    graph.add_node("write", write)
    graph.add_node("refuse", refuse)
    graph.add_edge(START, "search")
    graph.add_edge("search", "judge")
    graph.add_conditional_edges("judge", next_step, ["write", "refuse", "search_again"])
    graph.add_edge("search_again", "judge")
    graph.add_edge("write", END)
    graph.add_edge("refuse", END)
    return graph.compile()


def run(conn, client, question, embedding=DEFAULT_EMBEDDING):
    """Everything about one answer: the rounds, the chunks the writer saw, the answer, the check and the time of each kind of step."""
    final = build_graph(conn, client, embedding).invoke({"question": question, "rounds": []})
    written = final["written"]
    times = {}
    for record in final["rounds"]:
        for step, seconds in record["seconds"].items():
            times[step] = times.get(step, 0) + seconds
    times.update(written["seconds"])
    return {"question": question, "rounds": final["rounds"], "chunks": written["chunks"], "answer": written["answer"],
            "raw_answer": written["raw_answer"], "check": written["check"], "times": times, "tokens": written["tokens"],
            "refused_by_judge": written["refused_by_judge"], "laws_missing": final.get("laws_missing", []),
            "laws_found": final.get("laws_found", []), "variants": final.get("variants"), "first": final["first"], "model": client.chat_model}


def trace_lines(rounds):
    """The rounds, step by step, as lines of text."""
    width = 110
    lines = []
    for record in rounds:
        lines += ["", "=" * width, f"ROUND {record['round']}   ({', '.join(f'{k} {v:.1f} s' for k, v in record['seconds'].items())})", "=" * width, "SEARCHED"]
        for line in record["searched"]:
            lines.append(textwrap.fill(line, width, initial_indent="  ", subsequent_indent="    "))
        lines.append("JUDGE")
        verdicts = {v["n"]: v for v in record["verdicts"]}
        for chunk in record["chunks"]:
            v = verdicts[chunk["n"]]
            mark = "approved" if chunk["id"] in record["approved"] else "rejected"
            only = f", only for: {v['only_for']}" if v["only_for"] else ""
            replaced = f", replaced by [{v['replaced_by']}]" if v["replaced_by"] else ""
            lines.append(f"  [{chunk['n']}] {mark:8}  {chunk['citation'][:44]}, {chunk['article'] or '-'}  ({chunk['source']})")
            lines.append(f"       {v['relevance']}, applies: {v['applies']}{only}{replaced}. {v['reason']}")
        lines.append(f"DECISION: {record['decision']}" + (f". Missing: {record['missing']}" if record["missing"] else ""))
        if record.get("stopped_by_code"):
            lines.append("STOPPED BY THE CODE: an approved chunk answers directly, so the agent writes instead of searching again")
        if record["laws_named"]:
            lines.append("LAWS NAMED: " + ", ".join(record["laws_named"]))
    return lines


def print_result(result):
    print(f"\n{'=' * 110}\n{result['question']}\n{'=' * 110}\n{result['answer']}\n\nSOURCES")
    for c in result["chunks"]:
        print(f"  [{c['n']}] {c['id']}  {c['citation']}  {c['article'] or '-'}")
    if result["laws_missing"]:
        print("NOT IN OUR DATA: " + ", ".join(result["laws_missing"]))
    check = result["check"]
    state = "refusal" if check["refusal"] else ("OK" if check["ok"] else "FAILED")
    print(f"\nCITATION CHECK: {state}. {len(result['rounds'])} round(s), {sum(result['times'].values()):.0f} s: "
          + ", ".join(f"{k} {v:.1f} s" for k, v in result["times"].items()))
    for failure in check["failures"]:
        print(textwrap.fill(failure, 110, initial_indent="  FAIL  ", subsequent_indent="        "))


def main():
    parser = argparse.ArgumentParser(description="Answer a question through the agent loop.")
    parser.add_argument("question")
    parser.add_argument("--trace", action="store_true", help="show the rounds step by step")
    parser.add_argument("--embedding", choices=EMBEDDINGS, default=DEFAULT_EMBEDDING)
    args = parser.parse_args()
    with connect() as conn:
        result = run(conn, ModelClient.from_settings(), args.question, args.embedding)
    if args.trace:
        print("\n".join(trace_lines(result["rounds"])))
    print_result(result)


if __name__ == "__main__":
    friendly_errors(main)
