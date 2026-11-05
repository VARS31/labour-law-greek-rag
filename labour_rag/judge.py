"""The Judge: one model call that decides which chunks can be used, and what the agent does next.

The instructions are in prompts/judge.md. The answer is checked here, because a JSON schema fixes only its shape: a chunk the
model skipped still gets a verdict, a law it names must be cited in the chunks, and a "newer" chunk must really be newer.
"""

import json

from .ask import source_label
from .config import ROOT
from .law_mentions import find_mentions, law_name

PROMPT_FILE = ROOT / "prompts/judge.md"
RELEVANCE = ("relevant", "partly", "not_relevant")
APPLIES = ("yes", "no", "unclear")
MAX_WORDS = 4000    # of chunk text per call: about 12,000 tokens, which leaves room for the prompt and the answer in CHAT_NUM_CTX
# A chunk the model skipped, or an answer that can't be read: keep the chunk, because losing the right one costs more.
UNSURE = {"relevance": "partly", "applies": "unclear", "only_for": "", "replaced_by": 0, "reason": ""}


def schema(final_round):
    decisions = ["answer", "refuse"] if final_round else ["answer", "search_again", "refuse"]
    chunk = {"type": "object",
             "properties": {"n": {"type": "integer"}, "relevance": {"enum": list(RELEVANCE)}, "applies": {"enum": list(APPLIES)},
                            "only_for": {"type": "string"}, "replaced_by": {"type": "integer"}, "reason": {"type": "string"}},
             "required": ["n", "relevance", "applies", "only_for", "replaced_by", "reason"]}
    return {"type": "object",
            "properties": {"chunks": {"type": "array", "items": chunk}, "decision": {"enum": decisions}, "missing": {"type": "string"},
                           "references": {"type": "array", "items": {"type": "string"}}},
            "required": ["chunks", "decision", "missing", "references"]}


def system_prompt():
    return PROMPT_FILE.read_text(encoding="utf-8").strip()


def trimmed(text, max_words):
    words = text.split()
    return text if len(words) <= max_words else " ".join(words[:max_words]) + " …"


def user_message(question, chunks, round_number, max_rounds):
    """The question and the chunks. Eight full chunks fit, so text is only cut when a later round shows more than that."""
    max_words = MAX_WORDS // max(1, len(chunks))
    sources = "\n\n".join(f"[{c['n']}] {source_label(c)}\n{trimmed(c['text'], max_words)}" for c in chunks)
    last = " Είναι ο τελευταίος γύρος, άρα δεν μπορεί να γίνει νέα αναζήτηση." if round_number == max_rounds else ""
    return f"Γύρος {round_number} από {max_rounds}.{last}\n\nΕρώτηση: {question}\n\n{sources}\n\nJSON:"


def _verdict(entry):
    return {"relevance": entry["relevance"] if entry.get("relevance") in RELEVANCE else UNSURE["relevance"],
            "applies": entry["applies"] if entry.get("applies") in APPLIES else UNSURE["applies"],
            "only_for": str(entry.get("only_for") or "").strip(),
            "replaced_by": entry["replaced_by"] if isinstance(entry.get("replaced_by"), int) else 0,
            "reason": str(entry.get("reason") or "").strip()}


def _same_law(a, b):
    return a.number == b.number and (None in (a.year, b.year) or abs(a.year - b.year) <= 1)


def named_laws(references, chunks, question=""):
    """(kept, dropped): the laws in the model's references that the chunks or the question really cite, in the form chunk headers
    use. Matching digits aren't enough: "Β.Δ. 16/18 Ιουλ. 1920" is a decree cited by its date, not law number 16. A law cited in
    neither is the model's own memory, and the agent must not tell anyone about it."""
    cited = [m for text in [question] + [c["text"] for c in chunks] for m in find_mentions(text, any_year=True)]
    kept, dropped = [], []
    for reference in references:
        mentions = find_mentions(str(reference), any_year=True)
        if not mentions:
            dropped.append(str(reference))
        for mention in mentions:
            (kept if any(_same_law(mention, other) for other in cited) else dropped).append(law_name(mention))
    return list(dict.fromkeys(kept)), list(dict.fromkeys(dropped))


def parse_output(raw, chunks, final_round=False, question=""):
    """The model's answer as a clean dict. An unreadable answer keeps every chunk and goes on to the writer, with ok False."""
    numbers = {c["n"] for c in chunks}
    try:
        data = json.loads(raw)
        entries = {e["n"]: e for e in data["chunks"] if e.get("n") in numbers}
        decision = data["decision"]
        allowed = ("answer", "refuse") if final_round else ("answer", "search_again", "refuse")
        if decision not in allowed:
            raise ValueError("unknown decision")
        references = data["references"]
        missing = str(data.get("missing") or "").strip()
    except (ValueError, KeyError, TypeError, AttributeError):
        return {"verdicts": {n: dict(UNSURE) for n in sorted(numbers)}, "decision": "answer", "missing": "", "laws": [], "dropped_laws": [],
                "skipped": sorted(numbers), "ok": False}
    laws, dropped = named_laws(references if isinstance(references, list) else [], chunks, question)
    return {"verdicts": {n: _verdict(entries[n]) if n in entries else dict(UNSURE) for n in sorted(numbers)}, "decision": decision,
            "missing": missing, "laws": laws, "dropped_laws": dropped, "skipped": sorted(numbers - set(entries)), "ok": True}


def judge(client, question, chunks, round_number, max_rounds):
    """One call to the chat model, at temperature 0. The cleaned answer, the raw text and how many tokens it took."""
    final_round = round_number == max_rounds
    raw = client.chat([{"role": "system", "content": system_prompt()},
                       {"role": "user", "content": user_message(question, chunks, round_number, max_rounds)}],
                      response_format=schema(final_round), temperature=0)
    return {**parse_output(raw, chunks, final_round, question), "raw": raw, "tokens": dict(client.last_chat)}


def answers_directly(allowed, result):
    """True if an approved chunk answers the question and applies to this person: there's nothing left to search for."""
    verdicts = result["verdicts"]
    return any(verdicts[c["n"]]["relevance"] == "relevant" and verdicts[c["n"]]["applies"] == "yes" for c in allowed)


def approved(chunks, result):
    """The chunks the writer may see, best first: relevant or partly, and not ruled out for this person. A chunk replaced by a
    newer act goes, if that act is approved too and really is newer: the model can't be trusted on years, the data can."""
    verdicts = result["verdicts"]
    usable = {c["n"]: c for c in chunks if verdicts[c["n"]]["relevance"] != "not_relevant" and verdicts[c["n"]]["applies"] != "no"}

    def replaced(chunk):
        newer = usable.get(verdicts[chunk["n"]]["replaced_by"])
        return newer is not None and newer["n"] != chunk["n"] and None not in (newer["year"], chunk["year"]) and newer["year"] > chunk["year"]

    kept = [c for c in usable.values() if not replaced(c)]
    return sorted(kept, key=lambda c: verdicts[c["n"]]["relevance"] != "relevant")
