FROM gabrielv/kubruntudev:blender312

ENV PYTHONUNBUFFERED=1

# && apt-get clean \
RUN apt-get -yqq update \
&& apt-get -yqq install curl wget jq time redis-server fortune fortunes fortunes-* moreutils inotify-tools \
&& pip install --upgrade pip
# RUN update-rc.d redis-server defaults && update-rc.d redis-server enable

RUN pip install pipenv
ADD Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy --ignore-pipfile

RUN mkdir /app
WORKDIR /app
ENV PYTHONPATH="/app/kubric:/app:$PYTHONPATH"

RUN useradd --create-home --shell /bin/bash userino
RUN chown userino: /app
USER userino

