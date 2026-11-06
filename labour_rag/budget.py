"""The budget guard for paid model calls. Real usage is counted after every call and the running total is kept on disk, so a run
that stops and continues still counts what it spent before. A call that could pass a limit isn't made.

Local models cost nothing and don't come through here. Nothing about the API key ever reaches this file or the ledger.
"""

import json
import os
from pathlib import Path

from .config import ROOT

MODEL = "claude-haiku-5-5"
LEDGER = ROOT / "eval/haiku_spend.json"
RUN_LIMIT = 1.00        # dollars, per run
TOTAL_LIMIT = 3.00      # dollars, across all of Phase 4B
# Dollars per million tokens: platform.claude.com/docs/en/about-claude/pricing, checked on 2026-11-05. Prompts over 100,000 tokens
# cost more. We don't use caching, but a cached token would be billed and so it's counted.
SHORT_PROMPT = 100_000
SHORT_RATES = (0.10, 0.50)
LONG_RATES = (0.50, 2.50)
CACHE_WRITE = 1.25      # times the input rate
CACHE_READ = 0.1


def call_cost(input_tokens, output_tokens, cache_write=0, cache_read=0):
    """What one call costs in dollars. Output tokens include the model's thinking: that's what the API bills."""
    prompt = input_tokens + cache_write + cache_read
    per_input, per_output = SHORT_RATES if prompt <= SHORT_PROMPT else LONG_RATES
    return (per_input * (input_tokens + CACHE_WRITE * cache_write + CACHE_READ * cache_read) + per_output * output_tokens) / 1_000_000


class BudgetExceeded(RuntimeError):
    pass


class Budget:
    def __init__(self, run, path=LEDGER, run_limit=RUN_LIMIT, total_limit=TOTAL_LIMIT):
        self.run, self.path, self.run_limit, self.total_limit = run, Path(path), run_limit, total_limit

    def _ledger(self):
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {"total": 0.0, "runs": {}}

    def spent(self):
        """(this run, all runs), in dollars, as the ledger says now."""
        ledger = self._ledger()
        return ledger["runs"].get(self.run, {}).get("spent", 0.0), ledger["total"]

    def check(self, next_call_at_most=0.0):
        """Raises if the next call could take this run or the total past its limit."""
        run, total = self.spent()
        if run + next_call_at_most > self.run_limit:
            raise BudgetExceeded(f"this run has spent ${run:.4f} and the next call could cost ${next_call_at_most:.4f}: the limit per run is ${self.run_limit:.2f}")
        if total + next_call_at_most > self.total_limit:
            raise BudgetExceeded(f"all runs together have spent ${total:.4f} and the next call could cost ${next_call_at_most:.4f}: the limit is ${self.total_limit:.2f}")

    def add(self, cost, input_tokens, output_tokens):
        """Count one finished call. The file is replaced in one step, so stopping at any moment can't leave half a ledger."""
        ledger = self._ledger()
        entry = ledger["runs"].setdefault(self.run, {"spent": 0.0, "calls": 0, "input_tokens": 0, "output_tokens": 0})
        entry["spent"] = round(entry["spent"] + cost, 8)
        entry["calls"] += 1
        entry["input_tokens"] += input_tokens
        entry["output_tokens"] += output_tokens
        ledger["total"] = round(ledger["total"] + cost, 8)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(ledger, indent=1) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)
