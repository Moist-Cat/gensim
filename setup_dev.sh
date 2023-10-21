version="0.1.0"

echo "Setting up dev env..."
python -m venv env && \
    echo "
export PYTHONPATH='$PWD/src'
export FLASK_APP='$PWD/gensim/src/server.py'
export FLASK_DEBUG='1'
export GENSIM_SETTINGS_MODULE='gensim.conf.dev'
" >> $PWD/env/bin/activate && \
    echo "Variables added successfully" && \
source env/bin/activate && \
echo "Environment activated... installing stuff"
pip install -r requirements.txt && pip install -r requirements.dev.txt &&
echo "Job done"
