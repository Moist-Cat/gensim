# 

# Requirements
To install all requirements, use the following snippet after installing python on your machine.

    pip install -r requirements.txt

Or just use:

    pip install gensim


# Usage
Create database

    gensim migrate

Run server

    gensim runserver
    
Run client

    gensim-cli

# Development environment and testing

Use the 'setup\_dev.sh' script.

    ./setup_dev.sh
    source env/bin/activate
    ./gensim livetest

And ´./gensim test´ in another terminal


I use pytests to run the tests, along with black and pylint to lint the code.
To setup the environment use:

    venv env && pip install -r requirements.txt && pip install -r requirements.dev.txt

You should append the following enviroment variables to your ´env/bin/activate´ file.
´$ROOT´ is the root of the project; the directory with the ´setup.py´ file.

    # add the environment variables
    export PYTHONPATH='$ROOT/src'
    export FLASK_APP='$ROOT/src/server.py'
    export FLASK_DEBUG='1'
    export GENSIM_SETTINGS_MODULE='gensim.conf.dev'

If you get a "ModuleNotFoundError: gensim" your PYTHONPATH is probably wron. Use the VIRTUALENV variable in your ´activate´
file to get an idea of the path you need. Remove the "env" from that variable and you have your ROOT variable

Say VIRTUAL\_ENV is "VIRTUAL\_ENV='/home/anon/gensim/env'" you add "export ROOT=/home/anon/gensim" before the lines I mentioned before
and everything should work.

You can always run the commands with

    PYTHONPATH=$PWD/src FLASK_APP=$PWD/src/server.py FLASK_DEBUG=1 GENSIM_SETTINGS_MODULE=gensim.conf.dev ./gensim [command]

if none of the above work for you.
