"""config.json: the user's settings, with defaults. No imports from Jarvis's own modules, so any module (vault.py too,
which core.py imports) can read it."""
import json
import os
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
# JARVIS_CONFIG points to another config.json (the tests use one in a temporary folder).
CONFIG = pathlib.Path(os.environ.get("JARVIS_CONFIG") or HERE / "config.json")
DEFAULTS = {"voice": "Charon", "task_timeout": 300, "vault": str(pathlib.Path.home() / "Jarvis"), "port": 8765,
            "vision": False, "internet": True, "actions": True, "user_name": "Usuário",
            "city": {"name": "Rio de Janeiro", "region": "RJ, Brasil", "lat": -22.9068, "lon": -43.1729}}


def settings():
    s = dict(DEFAULTS)
    if CONFIG.exists():
        s.update(json.loads(CONFIG.read_text()))
    s["vault"] = os.path.expanduser(s["vault"])   # config.json may say "~/Jarvis"
    return s


def save_setting(key, value):
    s = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    s[key] = value
    tmp = CONFIG.with_suffix(".tmp")   # write then rename, so a crash never leaves a half-written config
    tmp.write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(CONFIG)


# The user's name, as Jarvis says it and as the transcripts label the user's turns. Read once at start: the prompts are
# built from it when the modules load, so a change in config.json takes effect after a restart.
USER = str(settings().get("user_name") or DEFAULTS["user_name"]).strip()
