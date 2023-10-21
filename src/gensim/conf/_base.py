from logging.config import dictConfig
from pathlib import Path
import sys

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# Config
DEBUG = False

# Logging
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
            "filename": BASE_DIR / "logs" / "api.error",
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
            "handlers": (
                "console",
                "audit_file",
            ),
            "level": "INFO" if DEBUG is False else "DEBUG",
        },
        "audit": {"handlers": ("audit_file",), "level": "ERROR"},
        "global": {
            "handlers": ("console",),
            "level": "INFO" if DEBUG is False else "DEBUG",
        },
    },
}
dictConfig(LOGGERS)
