"""What a Haiku run needs around the client: the key check before any search, the client for each system, and the manual runs of
`ask --haiku` and `agent --haiku`. In a file of its own, so that haiku_client.py and budget.py stay as they were when they were measured.
Only a run that asks for Haiku loads this file.
"""

from contextlib import contextmanager

import anthropic

from .budget import MODEL, Budget, BudgetExceeded
from .config import ROOT
from .haiku_client import KEY_NAME, HaikuClient, api_key
from .model_client import ModelClient, ModelError

# Manual runs have their own record and limit. data/ is gitignored, so demos don't show up as git changes, and
# eval/haiku_spend.json stays the record of the measuring runs only.
MANUAL_LEDGER = ROOT / "data/haiku_manual_spend.json"
MANUAL_LIMIT = 2.00     # dollars, across all manual runs


def check_key(sdk=None):
    """Stop with a clear message if the key is missing or rejected. Asking which model this is uses no tokens, so the check is free."""
    if sdk is None:
        key = api_key()
        if not key:
            raise SystemExit(f"{KEY_NAME} is not set. Put it in .env to use Haiku. Without Haiku, everything runs locally.")
        sdk = anthropic.Anthropic(api_key=key)
    try:
        sdk.models.retrieve(MODEL)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        raise SystemExit(f"Anthropic's API rejected {KEY_NAME}. Check the key in .env. Nothing was searched or sent.") from None
    except anthropic.NotFoundError:
        raise SystemExit(f"{KEY_NAME} works, but Anthropic's API doesn't offer {MODEL} to it.") from None
    except anthropic.APIError as error:
        raise SystemExit(f"Couldn't check {KEY_NAME} with Anthropic's API ({type(error).__name__}). Nothing was searched or sent.") from None


def failure_text(error):
    """What to tell the person about a ModelError from Haiku, or None if it came from the local models. Every Haiku failure names the
    model, and none of Ollama's does."""
    return f"{error}. If the key was rejected, check {KEY_NAME} in .env." if MODEL in str(error) else None


class MixedClient(HaikuClient):
    """Local Judge, Haiku Writer. The Judge and the Enhancer are the calls with a schema: they stay local, at their local settings."""

    def chat(self, messages, response_format=None, **options):
        if response_format:
            answer = self.local.chat(messages, response_format=response_format, **options)
            self.last_chat = self.local.last_chat
            return answer
        return super().chat(messages, **options)


CLIENTS = {"oneshot-haiku": HaikuClient, "agent-haiku": HaikuClient, "agent-mixed": MixedClient}


def client_for(system, local, budget):
    return CLIENTS[system](local, budget)


@contextmanager
def manual_run(who, sdk=None):
    """One question with Haiku from the command line: key check, what leaves the machine, the client, and the cost at the end."""
    check_key(sdk)
    print(f"{who}: Claude Haiku (cloud). The question and chunks leave this machine.", flush=True)
    MANUAL_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    budget = Budget("manual", MANUAL_LEDGER, MANUAL_LIMIT, MANUAL_LIMIT)
    before = budget.spent()[0]
    try:
        yield HaikuClient(ModelClient.from_settings(), budget, sdk)
    except BudgetExceeded as stop:
        raise SystemExit(f"Stopped by the budget guard for manual Haiku runs: {stop}.") from None
    except ModelError as error:
        text = failure_text(error)
        if text is None:
            raise       # a local failure, which friendly_errors explains
        raise SystemExit(text) from None
    spent = budget.spent()[0]
    print(f"\nThis question cost ${spent - before:.4f}. Manual Haiku runs so far: ${spent:.4f} of ${MANUAL_LIMIT:.2f}.")
