FROM gabrielv/kubruntudev:blender312

ENV PYTHONUNBUFFERED=1

# && apt-get clean \
RUN apt-get -yqq update \
&& apt-get -yqq install libfreeimage3 curl wget jq time redis-server fortune fortunes fortunes-* moreutils inotify-tools zip unzip ffmpeg \
&& pip install --upgrade pip
# RUN update-rc.d redis-server defaults && update-rc.d redis-server enable

RUN pip install pipenv
ADD Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy --ignore-pipfile

RUN mkdir /app
WORKDIR /app
ENV PYTHONPATH="/app/kubric:/app:$PYTHONPATH"
ENV THE_BLENDER_ROOT_PACKAGE="/usr/local/lib/python3.10/dist-packages/3.2"
ENV IMAGEIO_NO_INTERNET="True"

ADD addons $THE_BLENDER_ROOT_PACKAGE/scripts/addons

RUN useradd --create-home --shell /bin/bash userino
RUN chown userino: /app
USER userino
