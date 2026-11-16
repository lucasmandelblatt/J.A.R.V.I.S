"""Where Jarvis finds the programs and folders it uses. Each one can be set in config.json; without it, the program is
looked up in the same folders Jarvis gives its own subprocesses (core.TOOL_PATH), so a Mac with Homebrew in
/opt/homebrew or /usr/local and Claude Code in ~/.local/bin works without configuring anything.

    config.json key   what                                   default
    claude_path       Claude Code (research, long work)      found in core.TOOL_PATH
    ytdlp_path        yt-dlp (videos from other sites)       found in core.TOOL_PATH
    ffprobe_path      ffprobe (video length)                 found in core.TOOL_PATH
    atticus_path      Atticus's atticus.py (actions on Mac)  ~/Applications/Atticus.app/Contents/Resources/atticus.py
    app_path          the Jarvis app built by app/build.sh   ~/Applications/Jarvis.app

Read on every call, so a program installed (or a path changed) while Jarvis runs is picked up without a restart.
"""
import pathlib
import shutil

from core import HERE, TOOL_PATH, settings

HOME = pathlib.Path.home()


def _configured(key):
    value = settings().get(key)
    return pathlib.Path(value).expanduser() if value else None


def _program(key, name):
    """The configured path, else the first `name` in TOOL_PATH, else the bare name (running it then fails with
    FileNotFoundError, as a missing program did before)."""
    return str(_configured(key) or shutil.which(name, path=TOOL_PATH) or name)


def claude():
    return _program("claude_path", "claude")


def ytdlp():
    return _program("ytdlp_path", "yt-dlp")


def ffprobe():
    return _program("ffprobe_path", "ffprobe")


def atticus():
    return _configured("atticus_path") or HOME / "Applications/Atticus.app/Contents/Resources/atticus.py"


def app():
    return _configured("app_path") or HOME / "Applications/Jarvis.app"


def recorder():
    """The screen recorder inside the app (app/Gravar.swift)."""
    return app() / "Contents/MacOS/jarvis-gravar"


def code():
    """The folder with Jarvis's code (this one)."""
    return HERE


def vault():
    return pathlib.Path(settings()["vault"])
