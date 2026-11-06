"""Run ask, agent or evaluate as they are, with a trace of each question if TRACING is on in .env.

    .venv/bin/python -m labour_rag.traced agent "Πόσες μέρες άδεια δικαιούμαι;" --trace
    .venv/bin/python -m labour_rag.traced agent "Πόσες μέρες άδεια δικαιούμαι;" --haiku
    .venv/bin/python -m labour_rag.traced ask "Πόσες μέρες άδεια δικαιούμαι;"
    .venv/bin/python -m labour_rag.traced evaluate --split dev --system agent-haiku

Everything after the command name goes to that command. The plain commands stay exactly as they are and never trace, because they run only
frozen code. With TRACING off this runs the command and nothing else: OpenTelemetry isn't even loaded. See docs/observability.md.
"""

import importlib
import os
import sys

from .config import ROOT, _read_env_file
from .db import friendly_errors

COMMANDS = ("ask", "agent", "evaluate")
SWITCH = "TRACING"
ON = ("on", "true", "1", "yes")


def tracing_on(env_file=ROOT / ".env"):
    """Off unless the setting says otherwise. A value in the environment wins over the file, as with the other settings."""
    value = os.environ.get(SWITCH)
    if value is None:
        value = _read_env_file(env_file).get(SWITCH, "off")
    return value.strip().lower() in ON


def question_of(arguments):
    return next((a for a in arguments if not a.startswith("-")), "")


def system_of(command, arguments):
    if "--system" in arguments[:-1]:
        return arguments[arguments.index("--system") + 1]
    return "haiku" if "--haiku" in arguments else "local"


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        raise SystemExit(f"Usage: python -m labour_rag.traced {{{','.join(COMMANDS)}}} ...")
    command, arguments = sys.argv[1], sys.argv[2:]
    sys.argv = [f"{command}.py", *arguments]        # as if the command had been started by itself
    module = importlib.import_module(f"labour_rag.{command}")
    if not tracing_on():
        print(f"{SWITCH} is off, so this ran without a trace. Set {SWITCH}=on in .env to record one.", file=sys.stderr)
        friendly_errors(module.main)
        return

    from . import tracing as observability      # only with tracing on does OpenTelemetry get loaded
    tracing = observability.start()
    try:
        observability.instrument(tracing, command, arguments)
        try:
            friendly_errors(module.main)
        except SystemExit as stop:
            if isinstance(stop.code, str) and not tracing.trace_ids:
                tracing.record_failure(question_of(arguments), system_of(command, arguments), stop.code)
            raise
    finally:
        tracing.finish()
        for line in observability.links(tracing):
            print(line, file=sys.stderr)


if __name__ == "__main__":
    main()
