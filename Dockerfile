FROM python:3.12.1-slim-bookworm

# try to upgrade to a more recent version of openssl
RUN apt-get update
RUN apt-get -y upgrade openssl

# install jq
RUN apt-get -y install jq

# RUN sudo echo 'nameserver 8.8.8.8'>/etc/resolv.conf
RUN apt-get update -y
RUN apt-get install apt-file -y
RUN apt-file update
# RUN apt-get install -y python3-dev build-essential
RUN apt-get install -y procps

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --upgrade grpcio

ADD requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# install redis
RUN apt-get install -y redis-server

# install requirements
RUN python -m spacy download en_core_web_lg
RUN python -m nltk.downloader stopwords
RUN python -m nltk.downloader punkt

# Copy Swirl App to container
RUN mkdir /app
COPY ./db.sqlite3.dist /app/db.sqlite3
COPY ./.env.docker /app/.env
COPY ./install-ui.sh /app/install-ui.sh
ADD ./swirl /app/swirl

# Install Galaxy UI
RUN mkdir /app/swirl/static/galaxy
COPY --from=swirlai/spyglass:preview /usr/src/spyglass/ui/dist/spyglass/browser/. /app/swirl/static/galaxy
COPY --from=swirlai/spyglass:preview /usr/src/spyglass/ui/config-swirl-demo.db.json /app/

ADD ./swirl_server /app/swirl_server
ADD ./SearchProviders /app/SearchProviders
ADD ./scripts /app/scripts
ADD ./Data /app/Data
ADD ./swirl.py /app/swirl.py
ADD ./swirl_load.py /app/swirl_load.py
ADD ./manage.py /app/manage.py

WORKDIR /app

EXPOSE 8000
