Using Docker (experimental)
---------------------------
Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

The docker instructions for development are experimental, so they may
have bugs.  If you try them and run into any issues, please report
them!

You can also use Docker to run a Zulip development environment.
First, you need to install Docker in your development machine
following the [instructions][docker-install].  Some other interesting
links for somebody new in Docker are:

* [Get Started](https://docs.docker.com/engine/installation/linux/)
* [Understand the architecture](https://docs.docker.com/engine/understanding-docker/)
* [Docker run reference](https://docs.docker.com/engine/reference/run/)
* [Dockerfile reference](https://docs.docker.com/engine/reference/builder/)

[docker-install]: https://docs.docker.com/engine/installation/

Then you should create the Docker image based on Ubuntu Linux, first
go to the directory with the Zulip source code:

```
docker build -t user/zulipdev .
```


Commit and tag the provisioned images. The below will install Zulip's dependencies:
```
docker run -itv $(pwd):/srv/zulip -p 9991:9991 user/zulipdev /bin/bash
$ /usr/bin/python /srv/zulip/tools/provision.py --docker
docker ps -af ancestor=user/zulipdev
docker commit -m "Zulip installed" <container id> user/zulipdev:v2
```

Now you can run the docker server with:

```
docker run -itv $(pwd):/srv/zulip -p 9991:9991 user/zulipdev:v2 \
    /srv/zulip/tools/start-dockers
```

You'll want to
[read the guide for Zulip development](dev-env-first-time-contributors.html#step-4-developing)
to understand how to use the Zulip development.  Note that
`start-dockers` automatically runs `tools/run-dev.py` inside the
container; you can then visit http://localhost:9991 to connect to your
new Zulip Docker container.


To view the container's `run-dev.py` console logs to get important
debugging information (and e.g. outgoing emails) printed by the Zulip
development environment, you can use:
```
docker logs --follow <container id>
```

To restart the server use:
```
docker ps
docker restart <container id>
```

To stop the server use:
```
docker ps
docker kill <container id>
```

If you want to connect to the Docker instance to run commands
(e.g. build a release tarball), you can use:

```
docker ps
docker exec -it <container id> /bin/bash
$ source /home/zulip/.bash_profile
$ <Your commands>
$ exit
```

If you want to run all the tests you need to start the servers first,
you can do it with:

```
docker run -itv $(pwd):/srv/zulip user/zulipdev:v2 /bin/bash
$ tools/test-all-docker
```

You can modify the source code in your development machine and review
the results in your browser.


Currently, the Docker workflow is substantially less convenient than
the Vagrant workflow and less documented; please contribute to this
guide and the Docker tooling if you are using Docker to develop Zulip!
