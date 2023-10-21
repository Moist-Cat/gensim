from code import InteractiveConsole
import sys

from gensim.conf import settings
from gensim.db import *
from gensim.server import *
from gensim.api import Client
from gensim.management.db import get_save

if len(sys.argv) == 3:
    URL = get_save(sys.argv[2])
else:
    URL = settings.DATABASES["default"]["engine"]

client = Client(url=URL)

banner = """
#######################################
# gensim database interactive console #
#######################################
A Client instance is already defined (as 'client') and connected to the database.
Use it to make queries.
"""
i = InteractiveConsole(locals=locals())
i.interact(banner=banner)
