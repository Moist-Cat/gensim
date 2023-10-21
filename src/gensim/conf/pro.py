from gensim.conf._base import *
import os

HOST = "localhost"
PORT = "8888"

# Config
DEBUG = False
SAVES_DIR = BASE_DIR / "sav"

# Database
DATABASES = {
    "default": {"engine": f"sqlite:///{BASE_DIR}/db.sqlite", "config": {}},
    "play": {"engine": "sqlite:///" + str(BASE_DIR / "sav" / "db.save.{num}.gsav")},
}
