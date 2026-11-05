"""Measure the pipeline on the evaluation set (eval/questions.jsonl).

    .venv/bin/python -m labour_rag.evaluate --split dev                         # the current one-shot setup
    .venv/bin/python -m labour_rag.evaluate --split dev --max-per-document 4    # another chunk limit
    .venv/bin/python -m labour_rag.evaluate --split dev --retrieval-only        # search only, no model answer
    .venv/bin/python -m labour_rag.evaluate --split dev --retrieval-only --embedding bge-m3
    .venv/bin/python -m labour_rag.evaluate --split dev --fusion rrf            # another way of combining the lists
    .venv/bin/python -m labour_rag.evaluate --rescore eval/results/<run>        # score stored answers again

Each run writes eval/results/<date>_<config>/ with items.jsonl (one line per question, added as it finishes, so an
interrupted run continues), summary.json and summary.md. The test split runs once per named system, recorded in
eval/test_runs.json.
"""

import argparse
import datetime
import json
import statistics
import time
from pathlib import Path

from . import citations, enhancer, search
from .ask import NOTE_ADDED, ask, closing_note
from .config import ROOT
from .db import connect, friendly_errors
from .embeddings import DEFAULT_EMBEDDING, EMBEDDINGS, embed_question
from .key_facts import fact_present
from .model_client import ModelClient
from .retrieve import CONTEXT_CHUNKS, MAX_PER_DOCUMENT, NUMBER_RULE, NUMBER_RULES, POOL, select

QUESTIONS = ROOT / "eval/questions.jsonl"
RESULTS = ROOT / "eval/results"
TEST_RUNS = ROOT / "eval/test_runs.json"
CHUNKS = ROOT / "data/processed/labour_chunks.jsonl"
TOP = 50                # recall@50 and the rank for MRR look this far down the ranked list
FUSED = 100             # 2 lists of 50 candidates can give up to 100 chunks
CATEGORIES = ["single_source", "sector_trap", "vocabulary", "follow_reference", "must_refuse", "exact_lookup"]


def load_questions(split=None, ids=None, path=QUESTIONS):
    with Path(path).open(encoding="utf-8") as f:
        items = [json.loads(line) for line in f]
    return [i for i in items if (split is None or i["split"] == split) and (not ids or i["id"] in ids)]


def gold_chunks(item):
    return {c for source in item["gold_sources"] for c in source["chunk_ids"]}


def gold_documents(item):
    """Document numbers of the gold chunks: glc-41850-005 -> 41850."""
    return {int(c.split("-")[1]) for c in gold_chunks(item)}


def first_rank(results, wanted, rank_key="rank"):
    """The best rank any wanted chunk has in the results, or None."""
    ranks = [r[rank_key] for r in results if r["id"] in wanted and r.get(rank_key)]
    return min(ranks) if ranks else None


def score_retrieval(item, fused, kept, lists, removed=()):
    """Where the gold chunks ended up. `fused` is the ranked list, `kept` the chunks given to the model, `lists` the
    semantic and keyword lists before they were combined, `removed` what was left out while choosing the chunks."""
    wanted = gold_chunks(item)
    if not wanted:
        return None
    rank = first_rank(fused[:TOP], wanted)
    return {"rank": rank,
            "reciprocal_rank": 1 / rank if rank else 0.0,
            "in_context": any(c["id"] in wanted for c in kept),
            "in_top_50": rank is not None,
            "gold_law_in_context": any(c["doc_id"] in gold_documents(item) for c in kept),
            "semantic_rank": first_rank(lists["semantic"], wanted),
            "keyword_rank": first_rank(lists["keyword"], wanted),
            "removed_as": next((r["reason"] for r in removed if r["id"] in wanted), None)}


def score_answer(item, answer, chunks, check, note):
    """Key facts found, whether a gold law was cited, whether the check passed, and whether it was a refusal."""
    body = answer.replace(note, " ")
    facts = [{"fact": fact, "present": fact_present(fact, body)} for fact in item["key_facts"]] \
        if item["answerable"] else []
    documents = {c["n"]: c["doc_id"] for c in chunks}
    cited = {documents[n] for n in check["citations"] if n in documents}
    chunk_ids = {c["n"]: c["id"] for c in chunks}
    return {"facts": facts,
            "fact_share": sum(f["present"] for f in facts) / len(facts) if facts else None,
            "gold_law_cited": bool(cited & gold_documents(item)) if item["gold_sources"] else None,
            "gold_chunk_cited": bool({chunk_ids[n] for n in check["citations"] if n in chunk_ids} & gold_chunks(item))
            if item["gold_sources"] else None,
            "check_ok": check["ok"],
            "refused": check["refusal"]}


def problem(record):
    """Why an answer fell short, in the words of the report: search didn't bring the gold chunk to the model, or the
    model had it and still got it wrong. None when nothing fell short, or when the run has no answers."""
    if "answer" not in record:
        return None
    retrieval, score = record["retrieval"], record["score"]
    if record["answerable"]:
        if score["fact_share"] == 1 and not score["refused"]:
            return None
        return "search" if retrieval and not retrieval["in_context"] else "reading"
    if score["refused"]:
        return None
    return "reading"       # it answered a question the sources can't answer, whatever search brought back


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def _share(flags):
    flags = [f for f in flags if f is not None]
    return round(sum(map(bool, flags)) / len(flags), 3) if flags else None


def summarise_group(records):
    retrievals = [r["retrieval"] for r in records if r["retrieval"]]
    out = {"questions": len(records), "with_gold_chunks": len(retrievals),
           "recall_at_8": _share(r["in_context"] for r in retrievals),
           "recall_at_50": _share(r["in_top_50"] for r in retrievals),
           "mrr": _mean(r["reciprocal_rank"] for r in retrievals),
           "gold_law_in_context": _share(r["gold_law_in_context"] for r in retrievals),
           "semantic_recall_at_8": _share(r["semantic_rank"] is not None and r["semantic_rank"] <= CONTEXT_CHUNKS
                                          for r in retrievals),
           "semantic_recall_at_50": _share(r["semantic_rank"] is not None for r in retrievals),
           "semantic_mrr": _mean(1 / r["semantic_rank"] if r["semantic_rank"] else 0.0 for r in retrievals),
           "keyword_recall_at_50": _share(r["keyword_rank"] is not None for r in retrievals),
           "seconds_median": round(statistics.median(sum(r["times"].values()) for r in records), 3) if records else None}
    answered = [r for r in records if "answer" in r]
    if answered:
        answerable = [r for r in answered if r["answerable"]]
        unanswerable = [r for r in answered if not r["answerable"]]
        out.update({
            "answerable": len(answerable), "unanswerable": len(unanswerable),
            "fact_share": _mean(r["score"]["fact_share"] for r in answerable),
            "all_facts": _share(r["score"]["fact_share"] == 1 for r in answerable),
            "gold_law_cited": _share(r["score"]["gold_law_cited"] for r in answerable),
            "check_passed": _share(r["score"]["check_ok"] for r in answerable),
            "correct_refusals": sum(r["score"]["refused"] for r in unanswerable),
            "wrong_refusals": sum(r["score"]["refused"] for r in answerable),
            "search_problems": sum(problem(r) == "search" for r in answered),
            "reading_problems": sum(problem(r) == "reading" for r in answered),
        })
    return out


def summarise(records, config):
    return {"config": config,
            "overall": summarise_group(records),
            "by_category": {c: summarise_group([r for r in records if r["category"] == c])
                            for c in CATEGORIES if any(r["category"] == c for r in records)}}


def _cell(value, percent=True):
    if value is None:
        return "-"
    return f"{value:.0%}" if percent and isinstance(value, float) else str(value)


def summary_table(summary):
    """The summary as a Markdown table, one row per category and one for all questions."""
    rows = [("all", summary["overall"])] + list(summary["by_category"].items())
    with_answers = "fact_share" in summary["overall"]
    head = ["Category", "Questions", "Recall@8", "Recall@50", "MRR"]
    head += ["Key facts", "All facts", "Gold law cited", "Check passed", "Correct refusals", "Wrong refusals",
             "Search problems", "Reading problems"] if with_answers else []
    head += ["Median time (s)"]
    lines = ["| " + " | ".join(head) + " |", "|---|" + "---:|" * (len(head) - 1)]
    for name, group in rows:
        cells = [name, group["questions"], _cell(group["recall_at_8"]), _cell(group["recall_at_50"]),
                 "-" if group["mrr"] is None else f"{group['mrr']:.2f}"]
        if with_answers:
            cells += [_cell(group.get("fact_share")), _cell(group.get("all_facts")), _cell(group.get("gold_law_cited")),
                      _cell(group.get("check_passed")),
                      f"{group.get('correct_refusals', 0)} of {group.get('unanswerable', 0)}",
                      f"{group.get('wrong_refusals', 0)} of {group.get('answerable', 0)}",
                      group.get("search_problems", 0), group.get("reading_problems", 0)]
        cells.append(group["seconds_median"])
        lines.append("| " + " | ".join(map(str, cells)) + " |")
    return "\n".join(lines)


def write_summary(run_dir, records, config):
    summary = summarise(records, config)
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (run_dir / "summary.md").write_text(f"# {run_dir.name}\n\n{json.dumps(config, ensure_ascii=False)}\n\n"
                                        f"{summary_table(summary)}\n", encoding="utf-8")
    return summary


def read_records(run_dir):
    path = run_dir / "items.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def ranked_list(conn, client, question, embedding, fusion):
    """The ranked list for a question with the chosen embedding and fusion, the two lists it was made from, and the
    seconds per step."""
    started = time.perf_counter()
    vector = embed_question(client, question, embedding)
    after_embed = time.perf_counter()
    semantic = search.semantic(conn, client, question, search.CANDIDATES, vector, embedding)
    keyword = search.keyword(conn, question, search.CANDIDATES)
    fused = search.fuse(fusion, semantic, keyword, question, FUSED)
    return fused, {"semantic": semantic, "keyword": keyword}, {"embed question": after_embed - started,
                                                               "search": time.perf_counter() - after_embed}


def enhanced_list(conn, client, item, config, output):
    """Like ranked_list, through the Query Enhancer. A stored output saves the model call and keeps its measured time;
    its raw answer is read again, so the current checks apply."""
    if output:
        output = {**output, **enhancer.parse_output(output["raw"], item["question"])}
    else:
        output = enhancer.enhance(client, item["question"])
    started = time.perf_counter()
    question = item["question"] if enhancer.MODES[config["enhancer"]] else None
    fused, lists = enhancer.ranked(conn, client, output, question, FUSED, config["embedding"])
    return fused, lists, {"enhancer": output["seconds"], "search": time.perf_counter() - started}, output


def evaluate_item(conn, client, item, config, stored_output=None):
    """One question: where its gold chunks rank, and, unless this is a retrieval-only run, the answer and its scores."""
    max_per_document = config["max_per_document"]
    record = {key: item[key] for key in ("id", "category", "split", "answerable", "question")}
    if config.get("enhancer"):
        fused, lists, times, record["enhancer"] = enhanced_list(conn, client, item, config, stored_output)
    else:
        fused, lists, times = ranked_list(conn, client, item["question"], config["embedding"], config["fusion"])
    if config["retrieval_only"]:
        kept, removed = select(fused[:POOL], CONTEXT_CHUNKS, max_per_document, config["number_rule"])
        record["times"] = times
    else:
        result = ask(conn, client, item["question"], max_per_document=max_per_document, fusion=config["fusion"],
                     embedding=config["embedding"])
        kept, removed = result["chunks"], result["removed"]
        record.update({"times": result["times"], "answer": result["answer"], "check": result["check"],
                       "tokens": result["tokens"]})
        record["score"] = score_answer(item, result["answer"], kept, result["check"], closing_note())
    record["retrieval"] = score_retrieval(item, fused, kept, lists, removed)
    record["chunks"] = [{"n": c["n"], "id": c["id"], "doc_id": c["doc_id"], "citation": c["citation"],
                         "article": c["article"]} for c in kept]
    record["removed"] = {"near_duplicate": sum(r["reason"] == "near-duplicate" for r in removed),
                         "same_document": sum(r["reason"] == "same document" for r in removed)}
    return record


# Who may use the test split, and how each answers one question. Phase 4 adds the agent.
SYSTEMS = {"one-shot": evaluate_item}


def config_name(config):
    kind = "retrieval" if config["retrieval_only"] else "oneshot"
    embedding = f"-{config['embedding']}" if config["embedding"] != "bge-m3" or config["retrieval_only"] else ""
    # Runs before Phase 3B have no number rule in their name: they used the old repeat filter.
    rule = f"-{config['number_rule']}" if config.get("number_rule") else ""
    fusion = f"enhancer-{config['enhancer']}" if config.get("enhancer") else config["fusion"]
    return f"{kind}{embedding}-{fusion}{rule}-limit{config['max_per_document']}-{config['split']}"


def claim_test_run(system, run_name, path=TEST_RUNS, results=RESULTS):
    """The test split runs once per named system, so its numbers stay honest. A system's first run is recorded in
    eval/test_runs.json, and only that run, if unfinished, may continue. Returns the name of the run to use."""
    claims = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    claim = claims.get(system)
    if not claim:
        claims[system] = {"run": run_name, "started": run_name.split("_")[0]}
        path.write_text(json.dumps(claims, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return run_name
    if (results / claim["run"] / "summary.json").exists() or claim["run"].split("_", 1)[1] != run_name.split("_", 1)[1]:
        raise SystemExit(f"{system} has already used its run on the test split ({claim['run']}). It runs once per "
                         "system, so its numbers stay honest. Use the dev split for experiments.")
    return claim["run"]


def chunk_texts(path=CHUNKS):
    with Path(path).open(encoding="utf-8") as f:
        return {chunk["id"]: chunk["text"] for chunk in map(json.loads, f)}


def rescore(run_dir):
    """Check and score stored answers again with the current code and key facts. Needs no model and no database."""
    items = {i["id"]: i for i in load_questions()}
    texts = chunk_texts()
    records = read_records(run_dir)
    config = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))["config"]
    for record in records:
        if "answer" in record:
            chunks = [{**c, "text": texts[c["id"]]} for c in record["chunks"]]
            note_added = NOTE_ADDED in record["check"]["warnings"]      # ask() knows this; the answer no longer shows it
            record["check"] = citations.check(record["answer"], chunks, closing_note())
            if note_added:
                record["check"]["warnings"].append(NOTE_ADDED)
            record["score"] = score_answer(items[record["id"]], record["answer"], record["chunks"], record["check"],
                                           closing_note())
    with (run_dir / "items.jsonl").open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return write_summary(run_dir, records, config)


def run(args):
    config = {"split": args.split, "system": args.system, "fusion": args.fusion, "number_rule": args.number_rule,
              "enhancer": args.enhancer,
              "max_per_document": args.max_per_document, "embedding": args.embedding,
              "retrieval_only": args.retrieval_only, "context_chunks": CONTEXT_CHUNKS, "pool": POOL}
    run_name = f"{datetime.date.today():%Y-%m-%d}_{args.name or config_name(config)}"
    if args.split == "test":
        run_name = claim_test_run(args.system, run_name)
    run_dir = RESULTS / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    records = read_records(run_dir)
    done = {r["id"] for r in records}
    stored = {r["id"]: r["enhancer"] for r in read_records(args.reuse_enhancer)} if args.reuse_enhancer else {}
    items = [i for i in load_questions(args.split, set(args.ids.split(",")) if args.ids else None)
             if i["id"] not in done]

    client = ModelClient.from_settings()
    print(f"{run_dir.name}: {len(items)} questions to run, {len(done)} already done", flush=True)
    with connect() as conn:
        for position, item in enumerate(items, 1):
            record = SYSTEMS[args.system](conn, client, item, config, stored.get(item["id"]))
            records.append(record)
            with (run_dir / "items.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            retrieval = record["retrieval"]
            print(f"  {position}/{len(items)} {item['id']}: rank {retrieval['rank'] if retrieval else '-'}, "
                  f"{sum(record['times'].values()):.1f} s", flush=True)
    summary = write_summary(run_dir, records, config)
    print(summary_table(summary))
    print(f"wrote {run_dir}")


def main():
    parser = argparse.ArgumentParser(description="Measure the pipeline on the evaluation set.")
    parser.add_argument("--split", choices=["dev", "test"])
    parser.add_argument("--system", choices=SYSTEMS, default="one-shot", help="which system answers the questions")
    parser.add_argument("--fusion", choices=search.FUSIONS, default=search.DEFAULT_FUSION,
                        help="how semantic and keyword search are combined")
    parser.add_argument("--max-per-document", type=int, default=MAX_PER_DOCUMENT)
    parser.add_argument("--retrieval-only", action="store_true", help="search only, no model answer (fast)")
    parser.add_argument("--embedding", choices=EMBEDDINGS, default=DEFAULT_EMBEDDING,
                        help="vectors for semantic search; qwen3-4b-plain leaves out the query instruction")
    parser.add_argument("--number-rule", choices=NUMBER_RULES, default=NUMBER_RULE,
                        help="which numbers must match for two chunks to count as repeats")
    parser.add_argument("--enhancer", choices=enhancer.MODES, help="search through the Query Enhancer (with --retrieval-only)")
    parser.add_argument("--reuse-enhancer", type=Path, help="take the enhancer's outputs from this run instead of calling the model")
    parser.add_argument("--ids", help="only these questions, comma-separated (for a quick try, with --name)")
    parser.add_argument("--name", help="name of the run instead of the one made from its settings")
    parser.add_argument("--rescore", type=Path, help="score the stored answers of this run again")
    args = parser.parse_args()
    if args.rescore:
        print(summary_table(rescore(args.rescore)))
    elif not args.split:
        parser.error("--split is required, unless you use --rescore")
    else:
        if args.enhancer and not args.retrieval_only:
            parser.error("the enhancer isn't part of answering yet: use --retrieval-only")
        if args.split == "test" and (args.retrieval_only or args.ids):
            parser.error("a system's one test run must answer every question: no --retrieval-only or --ids")
        run(args)


if __name__ == "__main__":
    friendly_errors(main)
