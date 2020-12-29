FROM python:3.9-buster

COPY requirements.txt /opt/

WORKDIR /opt

RUN pip install -r requirements.txt

COPY *.py /opt/
COPY commands/*.py /opt/commands/

ENTRYPOINT ["python", "gogrepoc.py"]