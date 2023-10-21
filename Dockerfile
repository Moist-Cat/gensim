FROM python:3

COPY ./env/lib/python3.10/site-packages /usr/local/lib/python3.10/
COPY ./env/lib64/python3.10/site-packages /usr/local/lib64/python3.10/
COPY ./src/ .
