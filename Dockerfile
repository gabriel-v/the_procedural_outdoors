FROM gabrielv/kubruntudev:blender320-release

ENV PYTHONUNBUFFERED=1

# && apt-get clean \
RUN apt-get -yqq update \
&& apt-get -yqq install python3 python3.9 python3.9-dev python3-pip

# make python3.9 the default python and python3 so ubuntu doesn't break
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.9 10 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 10
ENV PYTHONPATH=/usr/lib/python310.zip:/usr/lib/python3.9:/usr/lib/python3.9/lib-dynload:/usr/local/lib/python3.9/dist-packages:/usr/lib/python3/dist-packages:/usr/lib/python3.9/site-packages
# install pip for python 3.9
# RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
#     python3.9 get-pip.py && \
#     rm get-pip.py

RUN apt-get -yqq install gnupg libfreeimage3 curl wget jq time redis-server fortune fortunes fortunes-* moreutils inotify-tools zip unzip ffmpeg build-essential   software-properties-common

# RUN update-rc.d redis-server defaults && update-rc.d redis-server enable
# RUN add-apt-repository ppa:graphics-drivers
# RUN apt-get -yqq update

# install cuda - ubuntu 20 - from https://developer.nvidia.com/cuda-downloads?target_os=Linux&target_arch=x86_64&Distribution=Ubuntu&target_version=20.04&target_type=deb_local

RUN wget -q https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-ubuntu2004.pin \
 && mv cuda-ubuntu2004.pin /etc/apt/preferences.d/cuda-repository-pin-600 \
 && wget -q https://developer.download.nvidia.com/compute/cuda/11.6.2/local_installers/cuda-repo-ubuntu2004-11-6-local_11.6.2-510.47.03-1_amd64.deb \
 && dpkg -i cuda-repo-ubuntu2004-11-6-local_11.6.2-510.47.03-1_amd64.deb \
 && apt-key add /var/cuda-repo-ubuntu2004-11-6-local/7fa2af80.pub \
 && apt-get update \
 && apt-get -y install cuda

# make python3.10 the default python and python3
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 10 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 10
ENV PYTHONPATH=/usr/lib/python310.zip:/usr/lib/python3.10:/usr/lib/python3.10/lib-dynload:/usr/local/lib/python3.10/dist-packages:/usr/lib/python3/dist-packages:/usr/lib/python3.10/site-packages

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
RUN apt-get -y install vim wget curl
RUN sed -i -E 's/name="memory" value=".+"/name="memory" value="2GiB"/g' /etc/ImageMagick-6/policy.xml
RUN sed -i -E 's/name="map" value=".+"/name="map" value="2GiB"/g' /etc/ImageMagick-6/policy.xml
RUN sed -i -E 's/name="area" value=".+"/name="area" value="2GiB"/g' /etc/ImageMagick-6/policy.xml
RUN sed -i -E 's/name="disk" value=".+"/name="disk" value="8GiB"/g' /etc/ImageMagick-6/policy.xml
USER userino
