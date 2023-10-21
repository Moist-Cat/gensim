#!/usr/bin/env python3
# import os
# import gensim
from gensim.management.manage import get_command

# from pathlib import Path

# env vars
# if "PYTHONPATH" not in os.environ or not os.environ["PYTHONPATH"]: # meaning we are not in a dev env
#    os.environ["FLASK_DEBUG"] = None
#    os.environ["FLASK_APP"] = str(Path(gensim.__file__).parent / "server.py")
#    os.environ["GENSIM_SETTINGS_MODULE"] = "gensim.conf.pro"

get_command()
