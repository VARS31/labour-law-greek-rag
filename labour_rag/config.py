"""Settings from .env (see .env.example). Values in the environment win over the file.

.env holds simple KEY=VALUE lines, so it is read here without an extra package.
"""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_env_file(path):
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("'\"")
    return values


@dataclass(frozen=True)
class Settings:
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    ollama_host: str
    embed_model: str
    embed_dim: int
    embed_batch: int


def load_settings(env_file=ROOT / ".env"):
    file_values = _read_env_file(Path(env_file))

    def get(key, default=None):
        value = os.environ.get(key, file_values.get(key, default))
        if value is None:
            raise KeyError(f"{key} is not set: copy .env.example to .env and fill it in")
        return value

    return Settings(
        postgres_host=get("POSTGRES_HOST", "localhost"),
        postgres_port=int(get("POSTGRES_PORT", "5433")),
        postgres_db=get("POSTGRES_DB"),
        postgres_user=get("POSTGRES_USER"),
        postgres_password=get("POSTGRES_PASSWORD"),
        ollama_host=get("OLLAMA_HOST", "http://localhost:11434"),
        embed_model=get("EMBED_MODEL", "bge-m3"),
        embed_dim=int(get("EMBED_DIM", "1024")),
        embed_batch=int(get("EMBED_BATCH", "16")),
    )
