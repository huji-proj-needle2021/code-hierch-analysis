# syntax=docker/dockerfile:1
FROM python:3.7-slim-buster

RUN apt-get update && apt-get install -y default-jre git

EXPOSE 8050
WORKDIR /app

COPY ./GRAPHS ./GRAPHS
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt && pip3 install gunicorn
COPY genCallgraph.jar genCallgraph.jar

COPY . .

CMD ["gunicorn"  , "--workers", "1", "--bind", "0.0.0.0:8050", "viz:server"]