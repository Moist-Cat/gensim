from gensim.conf._base import *

# Paths
TEST_DIR = Path(__file__).parent.parent / "test"
SAVES = TEST_DIR / "sav"

HOST = "localhost"
PORT = 14548

# Config
DEBUG = True
# whether the player can see interactions that don't concern him
TRUE_SIGHT = True

# Database
DATABASES = {
    "default": {
        "engine": "sqlite:///" + str(TEST_DIR / "test_db.sqlite3"),
    },
    "play": {
        "engine": "sqlite:///" + str(TEST_DIR / "sav" / "db.save.{num}.gsav"),
    },
}
