FROM python:3.9-buster

COPY requirements.txt /opt/

WORKDIR /opt

RUN pip install -r requirements.txt

COPY gogrepoc.py /opt/

ENTRYPOINT ["python", "gogrepoc.py"]