"""Logging methods"""
from typing import Callable
import logging
import logging.config

from gensim_cli import settings

logging.config.dictConfig(settings.LOGGERS)


def logged(cls) -> Callable:
    """Decorator to log certain methods of each class while giving
    each clas its own logger."""
    cls.logger = logging.getLogger("user_info." + cls.__qualname__)
    cls.logger_file = logging.getLogger("audit." + cls.__qualname__)

    return cls
