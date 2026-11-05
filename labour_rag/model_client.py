"""All calls to local models go through this module (Ollama's HTTP API, with Python's built-in urllib).

One place to change the model or the provider. The model names and settings come from .env (EMBED_MODEL,
CHAT_MODEL, …), so swapping a model is a configuration change.
"""

import json
import time
import urllib.error
import urllib.request

from .config import load_settings


class ModelError(RuntimeError):
    pass


class ModelClient:
    def __init__(self, host, embed_model, embed_dim=None, chat_model=None, chat_temperature=0.2,
                 chat_num_ctx=16384, chat_seed=None, timeout=600):
        self.host = host.rstrip("/")
        self.embed_model = embed_model
        self.embed_dim = embed_dim
        self.chat_model = chat_model
        self.chat_options = {"temperature": chat_temperature, "num_ctx": chat_num_ctx}
        if chat_seed is not None:
            self.chat_options["seed"] = chat_seed
        self.timeout = timeout
        self.tokens = 0          # embedding tokens sent so far (as counted by Ollama)
        self.seconds = 0.0       # time spent waiting for embeddings so far
        self.last_chat = {}      # tokens and timings of the last chat call

    @classmethod
    def from_settings(cls, settings=None):
        s = settings or load_settings()
        return cls(s.ollama_host, s.embed_model, s.embed_dim, s.chat_model, s.chat_temperature, s.chat_num_ctx,
                   s.chat_seed)

    def chat(self, messages, response_format=None, **options):
        """One answer from the chat model for a list of {"role", "content"} messages. Extra keyword arguments
        override the options from .env (e.g. temperature=0). response_format is a JSON schema the answer must follow:
        it fixes the shape of the answer, not what the model puts in it."""
        opts = {**self.chat_options, **options}
        started = time.perf_counter()
        payload = {"model": self.chat_model, "messages": messages, "stream": False, "options": opts}
        if response_format:
            payload["format"] = response_format
        data = self._post("/api/chat", payload)
        prompt_tokens = data.get("prompt_eval_count", 0)
        self.last_chat = {"seconds": time.perf_counter() - started, "prompt_tokens": prompt_tokens,
                          "answer_tokens": data.get("eval_count", 0),
                          "load_seconds": data.get("load_duration", 0) / 1e9, "done_reason": data.get("done_reason")}
        # Ollama silently drops the start of a prompt that doesn't fit the context window; refuse instead.
        if prompt_tokens + self.last_chat["answer_tokens"] >= opts["num_ctx"]:
            raise ModelError(f"the prompt ({prompt_tokens} tokens) filled the context window of {opts['num_ctx']}; "
                             "raise CHAT_NUM_CTX or send fewer chunks")
        return data["message"]["content"]

    def embed(self, texts, model=None, dim=None):
        """One embedding per text, from EMBED_MODEL unless another model and its vector size are given. A text longer
        than the model's context raises an error instead of being cut silently ("truncate": false)."""
        texts = list(texts)
        model, dim = model or self.embed_model, dim or self.embed_dim
        started = time.perf_counter()
        data = self._post("/api/embed", {"model": model, "input": texts, "truncate": False})
        self.seconds += time.perf_counter() - started
        self.tokens += data.get("prompt_eval_count", 0)
        vectors = data["embeddings"]
        if len(vectors) != len(texts):
            raise ModelError(f"asked for {len(texts)} embeddings, got {len(vectors)}")
        if dim and any(len(v) != dim for v in vectors):
            raise ModelError(f"{model} returned vectors of size {len(vectors[0])}, expected "
                             f"{dim} (EMBED_DIM and the vector column must match the model)")
        return vectors

    def _post(self, path, payload):
        request = urllib.request.Request(self.host + path, data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise ModelError(f"Ollama {path} failed ({error.code}): {error.read().decode()[:500]}") from None
        except urllib.error.URLError as error:
            raise ModelError(f"cannot reach Ollama at {self.host}: {error.reason}") from None
