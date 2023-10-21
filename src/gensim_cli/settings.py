"""Configurations for the http client"""
import warnings
import sys
import os
from pathlib import Path

try:
    import gensim
    from gensim.conf import settings
except ImportError:
    warnings.warn("Gensim is not installed... asuming remote host")

BASE_DIR = Path(__file__).resolve().parent

DEBUG = settings.DEBUG if gensim else "False"

# site config
HOST = os.environ.get("HOST", settings.HOST if gensim else "localhost")
PORT = os.environ.get("PORT", settings.PORT if gensim else "8000")
BASE_URL = f"http://{HOST}:{PORT}/api/"

# merely documentation
URLS = {
    # --- game urls ---
    "game/",
    "game/load/{num}",
    "game/save/{num}",
    # --- event urls ---
    "event/trigger/",
    # --- character urls ---
    "character/{name}/{attr}",
    # --- action urls ---
    "action/walk/",
    "action/chat/",
    "action/fish/",
    "action/cook/",
    # --- location urls
    "location/",
    "location/events",
}
URL_PARAMS = {
    "game",
    "load",
    "save",
    #
    "event",
    "trigger",
    "loop",
    #
    "action",
    "walk",
    "chat",
    "fish",
    "cook",
    #
    "character",
    "player",
    #
    "location",
    "events",
    "characters",
    #
    "area",
    "locations",
    "close_locations",
}

# data schemes
NEWGE_PAYLOAD = {"name": "", "energy": 0, "home": "", "location": ""}

WALK_PAYLOAD = {"character": "", "destination": ""}

# logger settings
LOGGERS = {
    "version": 1,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stderr,
            "formatter": "basic",
        },
        "audit_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 5000000,
            "backupCount": 1,
            "filename": BASE_DIR / "client.error",
            "encoding": "utf-8",
            "formatter": "basic",
        },
    },
    "formatters": {
        "basic": {
            "style": "{",
            "format": "{asctime:s} [{levelname:s}] -- {name:s}: {message:s}",
        }
    },
    "loggers": {
        "user_info": {
            "handlers": ("console",),
            "level": "DEBUG",
        },
        "audit": {"handlers": ("audit_file",), "level": "INFO"},
    },
}
