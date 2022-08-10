FROM rknop/devuan-chimaera-rknop
MAINTAINER Rob Knop <raknop@lbl.gov>

SHELL ["/bin/bash", "-c"]

RUN mkdir /home/stream
ENV HOME /home/stream

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y less python3 python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install \
   python-dateutil \
   requests \
   fastavro \
   confluent-kafka \
   && rm -rf /home/stream/.cache/pip

RUN mkdir /nightcache
RUN mkdir /alerts
RUN mkdir /elasticc
WORKDIR /home/stream
ADD stream-to-zads.py /home/stream/stream-to-zads.py

ENTRYPOINT [ "python3", "/home/stream/stream-to-zads.py" ]
