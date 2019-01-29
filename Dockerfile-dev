FROM ubuntu:trusty

EXPOSE 9991

RUN apt-get update && apt-get install -y wget

RUN localedef -i en_US -f UTF-8 en_US.UTF-8

RUN useradd -d /home/zulip -m zulip && echo 'zulip ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

USER zulip

RUN ln -nsf /srv/zulip ~/zulip
RUN echo 'export LC_ALL="en_US.UTF-8" LANG="en_US.UTF-8" LANGUAGE="en_US.UTF-8"' >> ~zulip/.bashrc
RUN echo 'export LC_ALL="en_US.UTF-8" LANG="en_US.UTF-8" LANGUAGE="en_US.UTF-8"' >> ~zulip/.bash_profile

WORKDIR /srv/zulip
