import os
import sys

from gensim.db import create_db
from gensim.conf import settings
from gensim.management import db
from gensim.test.test_ft import run_test_server
from gensim.server import runserver


def get_command(command: list = sys.argv[1]):
    """Macros to manage the db"""
    if command == "shell":
        import gensim.test.shell

    elif command == "migrate":
        create_db()

    elif command == "test":
        os.system(f"python -m pytest {settings.BASE_DIR / 'test'}")

    elif command == "runserver":
        runserver()

    elif command == "livetest":
        run_test_server()
    elif command == "setup":
        db.setup_database(name="anon")

    else:
        print(f"Bad command {command}")


if __name__ == "__main__":
    get_command()
