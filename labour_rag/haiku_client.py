"""Claude Haiku as the Judge and the Writer, through the official SDK. Local by default: only a run that asks for it comes here.

    .venv/bin/python -m labour_rag.haiku_client     # says whether the key is set, and makes one tiny call to confirm it works

With this client the question and the law chunks leave the machine. Search, embeddings and the Query Enhancer stay local. It has the same
chat() as model_client.ModelClient, so the agent and the one-shot run unchanged, with the same prompts. What can't stay the same: the
API takes no temperature or seed, so runs aren't exactly repeatable, and the model thinks at its default effort. Both are left to the
model on purpose. The key is read here and handed to the SDK. It is never printed, logged or stored.
"""

import os
import time

import anthropic

from . import enhancer
from .budget import MODEL, Budget, BudgetExceeded, call_cost
from .config import ROOT, _read_env_file
from .model_client import ModelError

KEY_NAME = "ANTHROPIC_API_KEY"
MAX_TOKENS = 16000      # thinking counts towards it, so this leaves plenty of room; a call that reaches it stops the run


def api_key():
    """The key, for the SDK only. Values in the environment win over .env, as with the other settings."""
    return os.environ.get(KEY_NAME) or _read_env_file(ROOT / ".env").get(KEY_NAME, "")


def strict_schema(schema):
    """A copy of a JSON schema with additionalProperties false on every object: the API requires it, and Ollama doesn't need it."""
    if isinstance(schema, list):
        return [strict_schema(value) for value in schema]
    if not isinstance(schema, dict):
        return schema
    strict = {key: strict_schema(value) for key, value in schema.items()}
    if strict.get("type") == "object":
        strict["additionalProperties"] = False
    return strict


class HaikuClient:
    """The Judge's and the Writer's calls go to Haiku. The Enhancer's call and all embeddings go to the local client."""

    chat_model = MODEL

    def __init__(self, local, budget, sdk=None):
        self.local, self.budget = local, budget
        self.sdk = sdk or anthropic.Anthropic(api_key=api_key())
        self.last_chat = {}

    def __getattr__(self, name):
        return getattr(self.local, name)        # embed, and what embedding keeps count of

    def chat(self, messages, response_format=None, **options):
        """One answer from Haiku. The options are for Ollama (temperature=0 from the Judge) and aren't passed on: the API rejects them.
        The Enhancer is recognised by its schema, which is the one thing that tells its call from the Judge's without changing either."""
        if response_format is enhancer.SCHEMA:
            answer = self.local.chat(messages, response_format=response_format, **options)
            self.last_chat = self.local.last_chat
            return answer
        request = {"model": MODEL, "max_tokens": MAX_TOKENS, "messages": [m for m in messages if m["role"] != "system"]}
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        if system:
            request["system"] = system
        if response_format:
            request["output_config"] = {"format": {"type": "json_schema", "schema": strict_schema(response_format)}}
        # A token is never less than half a character here, so this is the most the next call can cost.
        self.budget.check(call_cost(sum(len(m["content"]) for m in messages) // 2, MAX_TOKENS))
        started = time.perf_counter()
        try:
            response = self.sdk.messages.create(**request)
        except anthropic.APIError as error:
            raise ModelError(f"the call to {MODEL} failed: {type(error).__name__}: {getattr(error, 'message', '')}") from None
        return self._read(response, time.perf_counter() - started)

    def _read(self, response, seconds):
        """Count the call first, because it's billed whatever came back. Then the text: a response can begin with thinking blocks."""
        usage = response.usage
        cache_write, cache_read = usage.cache_creation_input_tokens or 0, usage.cache_read_input_tokens or 0
        cost = call_cost(usage.input_tokens, usage.output_tokens, cache_write, cache_read)
        prompt_tokens = usage.input_tokens + cache_write + cache_read
        self.budget.add(cost, prompt_tokens, usage.output_tokens)
        details = getattr(usage, "output_tokens_details", None)
        self.last_chat = {"seconds": seconds, "prompt_tokens": prompt_tokens, "answer_tokens": usage.output_tokens,
                          "thinking_tokens": getattr(details, "thinking_tokens", None), "load_seconds": 0.0,
                          "done_reason": response.stop_reason, "model": response.model, "cost": round(cost, 8)}
        if response.stop_reason != "end_turn":
            raise ModelError(f"{MODEL} stopped with {response.stop_reason}, so there is no complete answer to use")
        return "".join(block.text for block in response.content if block.type == "text")


def main():
    present = bool(api_key())
    print("key present:", "yes" if present else "no")
    if not present:
        raise SystemExit(f"Set {KEY_NAME} in .env to use Haiku.")
    budget = Budget("key-check")
    client = HaikuClient(None, budget)
    try:
        client.chat([{"role": "user", "content": "Reply with one word: ok"}])
    except (ModelError, BudgetExceeded) as error:
        raise SystemExit(f"key works: no. {error}") from None
    used = client.last_chat
    print(f"key works: yes. {used['model']}, {used['prompt_tokens']} tokens in, {used['answer_tokens']} out, {used['seconds']:.1f} s, ${used['cost']:.6f}")
    print(f"spent across all runs so far: ${budget.spent()[1]:.6f}")


if __name__ == "__main__":
    main()
