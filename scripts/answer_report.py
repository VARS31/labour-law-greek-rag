"""Phase 1C: answer the eight example questions one-shot and write docs/answer-report.md.

Needs the database (docker compose up -d), the loaded chunks and Ollama with the chat model.

Usage:
    .venv/bin/python scripts/answer_report.py                 # ask the model, store results, write the report
    .venv/bin/python scripts/answer_report.py --rewrite-only  # rewrite the report from the stored results
"""

import collections
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from labour_rag.ask import PROMPT_FILE, ask  # noqa: E402
from labour_rag.config import load_settings  # noqa: E402
from labour_rag.db import connect  # noqa: E402
from labour_rag.model_client import ModelClient  # noqa: E402
from labour_rag.retrieve import CONTEXT_CHUNKS, MAX_PER_DOCUMENT, NEAR_IDENTICAL, POOL, retrieve  # noqa: E402
from search_report import PROBE, QUESTIONS  # noqa: E402

REPORT = ROOT / "docs/answer-report.md"
RESULTS = ROOT / "data/processed/answer_results.json"

# Written by hand after reading each stored answer next to its chunks: (verdict, comment).
# Verdicts: correct, partly, wrong, wrongly refused, correctly refused.
ASSESSMENTS = {
    1: ("partly",
        "The direct answer is right: 24 working days, 20 with a five-day week, rising by one day per extra year to 26 "
        "or 22, as Α.Ν. 539/1945 art. 2 says since the 1983 replacement. The quote is real. Two flaws. Point 5 sets "
        "the 1981 minimum of 12 days (Υ.Α. 11282/1979) beside the 24 days as if both still applied, without saying "
        "that the 1979 text is older than the 1983 wording, and a reader can't tell which one counts. And "
        "\"εποχιακή\" is the model's word: the law says \"εκ περιτροπής\" (rotating work)."),
    2: ("partly",
        "Right: 8 hours a day and 48 a week (Ν.Δ. 1037/1971 art. 9), 9 and 54 by agreement for staff paid mainly by "
        "percentage, the butcher-shop table, the closing limits of 20:00, 21:00 and 18:00 (Κ.Υ.Α. 1162/1997) and the "
        "Sunday exceptions. Invented: the quote «Τα καταστήματα κλείνουν όταν κλείνουν οι πελάτες» and the claim "
        "that shops stop when customers leave (art. 7 only tolerates a 10-minute delay for customers already inside); "
        "\"Δεκαπενταύγουστο\" (the text says 20 December to 6 January and Holy Week); the examples of supermarkets and "
        "cafes. It doesn't mention that [8] leaves shops free to open at all hours except Sundays. The check rightly "
        "fails both quotes; the second is the real rule rewritten in modern Greek. Well over the length limit."),
    3: ("wrong",
        "The main point is reversed. Ν. 2112/1920 art. 3 gives full regular pay for the notice period when no notice "
        "was given, and a fraction (set at one half by Ν. 3198/1955 art. 4) when notice was given. The answer says "
        "one half when no notice was given. The payment rule is wrong too: the amount up to six months' pay is due on "
        "the dismissal day (Ν. 3198/1955 art. 2), not one month's. The 15% in point 4 limits only extra compensation "
        "at certain companies, and it is measured against Α.Ν. 99/1967, not Ν. 3198/1955. The validity conditions in "
        "point 3 are correct. The answer never gives the notice periods that decide the amount: they are in art. 1 of "
        "Ν. 2112/1920 (`glc-41850-005`), which isn't in the top 50 search results. The failed quote is close (96%): "
        "the model added \"δικαιούται\"."),
    4: ("wrong",
        "It presents 30%, 50% and 75% as the general rule under Ν.Δ. 515/1970 and says this doesn't cover ΚΤΕΛ staff. "
        "It's the reverse: those rates are in the ΚΤΕΛ decree (Π.Δ. 119/1973 art. 5, [1]). The quoted sentence comes "
        "from that decree as well, not from [2], so the check rightly fails it. The chunk of Ν.Δ. 515/1970 only has "
        "75% for specially permitted overtime and points to Ν. 435/1976 for the general rate, and I found no chunk "
        "under that citation. A correct answer would say that the rates found are per sector, and pass on that "
        "pointer. The bakers' 25%, 50% and 75% and the 75% for urgent cases are right. \"240 hours for ΚΤΕΛ\" leaves "
        "out that 120 is the normal limit and 240 the limit with exceptions."),
    5: ("partly",
        "Close in substance: under 15, work is allowed only in artistic and advertising activities with an "
        "Inspectorate permit (Ν. 1837/1989 art. 3), from age 3 and for up to 3 months a year under Π.Δ. 62/1998 "
        "art. 5. But the short answer leads with the exception and gives the general limit of 15 last, with no "
        "source. The quote has no citation, so the check fails it, although its words are in [1]. Two errors: 6 hours "
        "and 30 a week apply only to teens under 16 or at school, the general limit being 8 and 40 (Π.Δ. 62/1998 "
        "art. 3); and no chunk says that these laws repeal the older ones (\"αναιρούν\")."),
    6: ("wrong",
        "The check passes and the answer is still wrong. It applies Π.Δ. 16/1996 to building sites, yet art. 1 par. 5 "
        "of that decree, which the model received as [8], says it doesn't apply to \"προσωρινά ή κινητά εργοτάξια\". "
        "The fire rules come from Π.Δ. 70/1990, on shipyards. The second quote is about workers at their posts, not "
        "buildings. Only the ladder rule [7] is near the topic, and it leaves out the 9-metre limit. No chunk is "
        "about building sites, because search missed the topic: see the search report on \"οικοδομές\" against "
        "\"εργοτάξια\", and in this dataset Π.Δ. 305/1996 is only a header. The right answer was «Δεν βρέθηκε…», or "
        "a clear warning that only general rules turned up."),
    7: ("wrong",
        "The main rule is missing. Art. 1 of Κ.Υ.Α. 19040/1981 gives one month's salary or 25 daily wages for a full "
        "period from 1 May to 31 December, and art. 3 bases it on the pay of 10 December. The answer gives art. 4 "
        "instead, which covers only certain groups such as those on variable pay, and opens as if it were the rule "
        "for everyone. The cause is retrieval: art. 3 (rank 4) and art. 1 (rank 7) were dropped by the limit of 2 "
        "chunks per document. The details are mostly accurate for the groups they concern (the average-wage formula, "
        "one daily wage per five for raisin packers, night and Sunday pay counted). But \"6 months\" is invented, no "
        "law or year is named, and the quote is slightly altered (\"το μέσο όρου\")."),
    8: ("partly",
        "It points the right way (Π.Δ. 176/1997 does ban some exposures), but the main protections are missing: 16 "
        "weeks of maternity leave (Π.Δ. "
        "176/1997 art. 8, rank 8, dropped by the limit of 2 chunks per document), paid time off for prenatal exams "
        "(art. 9, rank 27), and the ban on dismissal and the night-work rule (arts. 10 and 7, not in the top 50). The "
        "check passes, but the one quote comes from [5], a decree on drilling industries. The exposure ban cites "
        "chunks that don't say it for pregnant workers: [2] is art. 6 cut off mid-sentence, where the source text "
        "breaks, and [4] and [6] are general rules on asbestos and lead. The exception \"unless absolutely necessary\" "
        "is invented. No law or year is named."),
}
OVERALL = """\
None of the eight answers is fully correct: four are partly right and four are wrong. The model never refused, not \
even on the construction question, which its chunks can't answer. I judged each answer against the text of its chunks \
only, not against current law. "Correct" means the direct answer is right and nothing important misleads. "Partly" \
means it is useful but has errors or big gaps. "Wrong" means the reader would be misled on the main point.

**What goes wrong**

- **The model mixes things up.** Rules for one sector or group become general rules (4, 6, 7, 8), cases get swapped \
(3), and details are invented (2, 7, 8). I haven't tried a larger model, so I can't say how much of this comes down \
to the size of this one.
- **Retrieval leaves out the answer.** The limit of 2 chunks per document removed the main rule in question 7 and \
maternity leave in question 8 (details in the section on repeats). In questions 3 and 6, search never found the key \
text.
- **A passing check doesn't mean a right answer.** It proves that quoted words exist in the cited chunk. It says \
nothing about the sentences around them. Questions 1, 6 and 8 pass, and question 6 is wrong. A failed check is a real \
warning, though: every failed quote here was altered, invented, cited to the wrong chunk, or had no citation.

**The prompt was revised once.** The first run was far from the short answers asked for, so I capped the explanation \
at five sentences, limited quotes to fifteen words in a row, banned made-up examples and calculations, and required \
sector rules to be labelled. The answers below are from the revised prompt. The first run is kept locally in \
`data/processed/answer_results_v1.json`.

| | First prompt | Revised prompt |
|---|---:|---:|
| Answers passing the check | 0 of 8 | 3 of 8 |
| Quotes found in the cited chunk | 17 of 42 (40%) | 4 of 10 (40%) |
| Median answer length | 949 tokens | 597 tokens |
| Median time per question | 64 s | 53 s |
| Closing note added by the code | 0 | 3 |

The answers got shorter, though question 2 still runs long. More of them pass only because the model quotes less: the \
share of good quotes didn't change. The invented calculation in question 7 went away, but sector rules are still \
presented as general. I stopped at one revision so as not to tune the prompt to these eight questions; further changes should be \
measured on the Phase 2 evaluation set."""
LIMIT_NOTE = """\
The per-document limit is the one that cost something. Re-running only the selection step on the same search results \
shows what a higher limit would let in (no model call was made, so this says nothing yet about the answers):

| Question | Chunk that the limit of 2 removed | Hybrid rank | Limit that lets it in |
|---|---|---:|---:|
| Christmas bonus | Κ.Υ.Α. 19040/1981 art. 3, pay of 10 December | 4 | 3 |
| Christmas bonus | Κ.Υ.Α. 19040/1981 art. 1, one month's salary or 25 daily wages | 7 | 4 |
| Maternity protection | Π.Δ. 176/1997 art. 8, maternity leave | 8 | 4 |

The limit of 2 stays as requested. A limit of 4 is worth testing on the Phase 2 evaluation set, because a higher limit \
also pushes other documents out of the eight. Near-duplicate removal did its job: in the Christmas bonus question, the \
twelve chunks it skipped are the same bonus decision re-issued in other years."""


def esc(text):
    return re.sub(r"([\\`*_\[\]<>|])", r"\\\1", text)


def run():
    client = ModelClient.from_settings()
    out = {"model": client.chat_model, "options": client.chat_options, "prompt": PROMPT_FILE.read_text("utf-8"),
           "questions": []}
    with connect() as conn:
        for question, topic in QUESTIONS:
            r = ask(conn, client, question, fusion="rrf", embedding="bge-m3")     # the setup this report describes
            r.pop("messages")
            out["questions"].append({"topic": topic, **r})
            print(f"{topic}: {sum(r['times'].values()):.1f} s, check {'OK' if r['check']['ok'] else 'FAILED'}")
        kept, removed, _ = retrieve(conn, client, PROBE, fusion="rrf", embedding="bge-m3")
        out["probe"] = {"question": PROBE, "kept": kept, "removed": removed}
    RESULTS.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return out


def blockquote(text):
    return "\n".join("> " + line if line.strip() else ">" for line in text.strip().split("\n"))


def write(out):
    qs = out["questions"]
    s = load_settings()
    L = []
    add = L.append
    add("# Answer report: one-shot answers with checked citations (Phase 1C)\n")
    add("The eight example questions from the search report, each answered with one model call from the chunks "
        "that search found. This file is generated by [`scripts/answer_report.py`](../scripts/answer_report.py) "
        "from stored results (`data/processed/answer_results.json`); the assessment under each answer was written "
        "by hand after reading the answer next to its sources.\n")

    verdicts = collections.Counter(ASSESSMENTS.get(i, ("not assessed",))[0] for i in range(1, len(qs) + 1))
    add("## At a glance\n")
    add("| # | Question | Verdict | Citation check | Quotes found | Time |\n|---:|---|---|---|---:|---:|")
    for i, e in enumerate(qs, 1):
        c = e["check"]
        found = sum(bool(q["found_in"]) for q in c["quotes"])
        state = "refusal" if c["refusal"] else ("OK" if c["ok"] else f"failed ({len(c['failures'])})")
        add(f"| {i} | {e['topic']} | {ASSESSMENTS.get(i, ('–',))[0]} | {state} | {found} of {len(c['quotes'])} | "
            f"{sum(e['times'].values()):.0f} s |")
    add("")
    add("Verdicts: " + ", ".join(f"{v} {n}" for v, n in verdicts.most_common()) + ".")
    times = [sum(e["times"].values()) for e in qs]
    model_times = [e["times"]["model answer"] for e in qs]
    add(f"Time per question: median {statistics.median(times):.0f} s, of which the model "
        f"{statistics.median(model_times):.0f} s; search and checking together take well under a second.\n")
    if OVERALL:
        add(OVERALL + "\n")

    add("## How an answer is made\n")
    add(f"1. **Search:** hybrid search (semantic + keyword, Reciprocal Rank Fusion) returns its top {POOL} chunks.")
    add(f"2. **Remove repeats:** walking down that list, a chunk is skipped if at least {NEAR_IDENTICAL:.0%} of its "
        f"words are shared with a chunk already chosen, or if its document already has {MAX_PER_DOCUMENT} chunks. "
        f"The first {CONTEXT_CHUNKS} that pass are numbered [1] to [{CONTEXT_CHUNKS}].")
    add(f"3. **Answer:** one call to `{out['model']}` through Ollama, temperature {out['options']['temperature']}, "
        f"seed {out['options'].get('seed')} (so the answer can be repeated), context window "
        f"{out['options']['num_ctx']:,} tokens. The instructions are in [`prompts/answer.md`](../prompts/answer.md); "
        "the chunks follow the question, each with its source, article, title and year.")
    add("4. **Closing note:** the fixed note from `prompts/closing_note.md` must end the answer; the code adds it "
        "if the model forgot.")
    add("5. **Citation check** (`labour_rag/citations.py`): every [n] must point to one of the chunks given; every "
        "quote in «…» must carry a citation and its words must appear in that chunk (accents, case and punctuation "
        "ignored; \"…\" may skip words). An answer that isn't a refusal must cite something. Warnings, which don't "
        "fail the check: sentences without a citation, no year named, closing note missing. When a quote fails, "
        "the most similar passage of the chunk is shown with its similarity, to tell a quote with small changes "
        "from one that isn't there.\n")

    add("## How often removing repeats changed the chunks\n")
    add("| Question | Near-duplicates skipped | Over the per-document limit |\n|---|---:|---:|")
    rows = [(e["topic"], e["removed"]) for e in qs] + [("probe: ILO convention clauses", out["probe"]["removed"])]
    for topic, removed in rows:
        dup = sum(r["reason"] == "near-duplicate" for r in removed)
        add(f"| {topic} | {dup} | {len(removed) - dup} |")
    any_dup = sum(any(r["reason"] == "near-duplicate" for r in e["removed"]) for e in qs)
    any_doc = sum(any(r["reason"] == "same document" for r in e["removed"]) for e in qs)
    add("")
    add(f"On the eight questions, near-duplicates were skipped for {any_dup} and the per-document limit applied "
        f"for {any_doc}. Chunks are counted only until the eighth one is chosen. The last row is the extra question "
        "from the search report about the standard ILO clauses (search only, no answer), where the top results are "
        "the same clause from many conventions. Examples of skipped chunks:\n")
    shown = 0
    for topic, removed in rows:
        for r in removed:
            if shown < 5 and r["reason"] == "near-duplicate":
                add(f"- *{topic}*: `{r['id']}` ({esc(r['citation'][:50])}, {esc(r['article'] or '-')}) skipped "
                    f"as a near-duplicate of `{r['of']}`")
                shown += 1
    add("")
    add(LIMIT_NOTE + "\n")

    add("## The eight answers\n")
    for i, e in enumerate(qs, 1):
        c = e["check"]
        add(f"### {i}. {e['topic'].capitalize()}\n")
        add(f"**Question:** {e['question']}\n")
        add(blockquote(e["answer"]) + "\n")
        add("**Sources given to the model**\n")
        add("| [n] | Chunk | Source | Article |\n|---:|---|---|---|")
        for ch in e["chunks"]:
            flags = " (editorial note)" if ch["is_note"] else ""
            add(f"| {ch['n']} | `{ch['id']}` | {esc(ch['citation'])} | {esc(ch['article'] or '-')}{flags} |")
        add("")
        cited = ", ".join(f"[{n}]" for n in c["citations"]) or "none"
        add(f"**Citation check: {'refusal' if c['refusal'] else ('OK' if c['ok'] else 'FAILED')}.** Cited: {cited}. "
            f"Quotes: {len(c['quotes'])}, found in the cited source: {sum(bool(q['found_in']) for q in c['quotes'])}.")
        for f in c["failures"]:
            add(f"- Failed: {esc(f)}")
        for w in c["warnings"]:
            add(f"- Warning: {esc(w)}")
        add("")
        steps = ", ".join(f"{k} {v:.2f} s" for k, v in e["times"].items())
        add(f"**Time:** {sum(e['times'].values()):.1f} s ({steps}); {e['tokens'].get('prompt_tokens', 0):,} prompt "
            f"tokens, {e['tokens'].get('answer_tokens', 0):,} answer tokens.\n")
        if i in ASSESSMENTS:
            verdict, comment = ASSESSMENTS[i]
            add(f"**Assessment: {verdict}.** {comment}\n")
    REPORT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")


def main():
    out = json.loads(RESULTS.read_text(encoding="utf-8")) if "--rewrite-only" in sys.argv else run()
    write(out)


if __name__ == "__main__":
    main()
