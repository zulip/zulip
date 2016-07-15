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

Now you're going to install Zulip dependencies in the image:

```
docker run -itv $(pwd):/srv/zulip -p 9991:9991 user/zulipdev /bin/bash
$ /usr/bin/python /srv/zulip/tools/provision.py --docker
docker ps -af ancestor=user/zulipdev
docker commit -m "Zulip installed" <container id> user/zulipdev:v2
```

Finally you can run the docker server with:

```
docker run -itv $(pwd):/srv/zulip -p 9991:9991 user/zulipdev:v2 \
    /srv/zulip/tools/start-dockers
```

If you want to connect to the Docker instance to build a release
tarball you can use:

```
docker ps
docker exec -it <container id> /bin/bash
$ source /home/zulip/.bash_profile
$ <Your commands>
$ exit
```

To stop the server use:
```
docker ps
docker kill <container id>
```

If you want to run all the tests you need to start the servers first,
you can do it with:

```
docker run -itv $(pwd):/srv/zulip user/zulipdev:v2 /bin/bash
$ tools/test-all-docker
```

You can modify the source code in your development machine and review
the results in your browser.
