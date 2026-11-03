"""All calls to local models go through this module (Ollama's HTTP API, with Python's built-in urllib).

One place to change the model or the provider. The model names come from .env (EMBED_MODEL), so swapping
bge-m3 for another embedding model is a configuration change. Phase 1C will add the chat model here.
"""

import json
import time
import urllib.error
import urllib.request

from .config import load_settings


class ModelError(RuntimeError):
    pass


class ModelClient:
    def __init__(self, host, embed_model, embed_dim=None, timeout=600):
        self.host = host.rstrip("/")
        self.embed_model = embed_model
        self.embed_dim = embed_dim
        self.timeout = timeout
        self.tokens = 0          # tokens sent so far (as counted by Ollama)
        self.seconds = 0.0       # time spent waiting for the model so far

    @classmethod
    def from_settings(cls, settings=None):
        s = settings or load_settings()
        return cls(s.ollama_host, s.embed_model, s.embed_dim)

    def embed(self, texts):
        """One embedding per text. A text longer than the model's context raises an error instead of being
        cut silently ("truncate": false)."""
        texts = list(texts)
        started = time.perf_counter()
        data = self._post("/api/embed", {"model": self.embed_model, "input": texts, "truncate": False})
        self.seconds += time.perf_counter() - started
        self.tokens += data.get("prompt_eval_count", 0)
        vectors = data["embeddings"]
        if len(vectors) != len(texts):
            raise ModelError(f"asked for {len(texts)} embeddings, got {len(vectors)}")
        if self.embed_dim and any(len(v) != self.embed_dim for v in vectors):
            raise ModelError(f"{self.embed_model} returned vectors of size {len(vectors[0])}, expected "
                             f"{self.embed_dim} (EMBED_DIM and the vector column must match the model)")
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
