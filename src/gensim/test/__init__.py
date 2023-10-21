import os
import logging
from pathlib import Path

from gensim.conf import Settings

settings = Settings("gensim.conf.dev")

logger = logging.getLogger("user-info.test")

db = settings.DATABASES["default"]
ENGINE = db["engine"]
