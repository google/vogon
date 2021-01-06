FROM ubuntu:18.04

RUN apt-get update \
  && apt-get install -y python3-pip python3-dev \
  && cd /usr/local/bin \
  && ln -s /usr/bin/python3 python \
  && pip3 install --upgrade pip

WORKDIR /app
COPY . /app
EXPOSE 8080

RUN apt-get install -y \
  libcurl4-openssl-dev \
  libssl-dev \
  ffmpeg \
  imagemagick

RUN pip3 install -r requirements.txt

CMD ["python3", "server.py", "--debug"]

