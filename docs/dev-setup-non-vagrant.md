# Zulip development environment setup without Vagrant

Contents:

* [Installing directly on Ubuntu](#installing-directly-on-ubuntu)
* [Installing manually on Linux](#installing-manually-on-linux)
* [Using Docker (experimental)](#using-docker-experimental)

## Installing directly on Ubuntu

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

If you'd like to install a Zulip development environment on a computer
that's already running Ubuntu 14.04 Trusty or Ubuntu 16.04 Xenial, you
can do that by just running:

```
# From a clone of zulip.git
./tools/provision
source /srv/zulip-py3-venv/bin/activate
./tools/run-dev.py  # starts the development server
```

Note that there is no supported uninstallation process without Vagrant
(with Vagrant, you can just do `vagrant destroy` to clean up the
development environment).

Once you've done the above setup, you can pick up the [documentation
on using the Zulip development
environment](dev-env-first-time-contributors.html#step-4-developing),
ignoring the parts about `vagrant` (since you're not using it).

## Installing manually on Linux

* [Debian or Ubuntu systems](#on-debian-or-ubuntu-systems)
* [Fedora 22 (experimental)](#on-fedora-22-experimental)
* [CentOS 7 Core (experimental)](#on-centos-7-core-experimental)
* [OpenBSD 5.8 (experimental)](#on-openbsd-5-8-experimental)
* [Fedora/CentOS common steps](#common-to-fedora-centos-instructions)
* [Steps for all systems](#all-systems)

If you really want to install everything manually, the below instructions
should work.

Install the following non-Python dependencies:
 * libffi-dev — needed for some Python extensions
 * postgresql 9.1 or later — our database (client, server, headers)
 * nodejs 0.10 (and yarn)
 * memcached (and headers)
 * rabbitmq-server
 * libldap2-dev
 * python3-dev
 * python-dev
 * python-virtualenv
 * redis-server — rate limiting
 * tsearch-extras — better text search
 * libfreetype6-dev — needed before you pip install Pillow to properly generate emoji PNGs

### On Debian or Ubuntu systems:

#### Using the official Ubuntu repositories, PGroonga PPA and `tsearch-extras` deb package:

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
sudo apt-get install closure-compiler libfreetype6-dev libffi-dev \
    memcached rabbitmq-server libldap2-dev redis-server \
    postgresql-server-dev-all libmemcached-dev python3-dev \
    python-dev python-virtualenv hunspell-en-us nodejs \
    nodejs-legacy git yui-compressor puppet gettext postgresql

# If using Ubuntu, install PGroonga from its PPA
sudo add-apt-repository -ys ppa:groonga/ppa
sudo apt-get update
# On 14.04
sudo apt-get install postgresql-9.3-pgroonga
# On 16.04
sudo apt-get install postgresql-9.5-pgroonga

# If using Debian, follow the instructions here: http://pgroonga.github.io/install/debian.html

# Next, install Zulip's tsearch-extras postgresql extension
# If on 14.04 or 16.04, you can use the Zulip PPA for tsearch-extras:
cd zulip
sudo apt-add-repository -ys ppa:tabbott/zulip
sudo apt-get update
# On 14.04
sudo apt-get install postgresql-9.3-tsearch-extras
# On 16.04
sudo apt-get install postgresql-9.5-tsearch-extras


# Otherwise, you can download a .deb directly
# If on 12.04 or wheezy:
wget https://dl.dropboxusercontent.com/u/283158365/zuliposs/postgresql-9.1-tsearch-extras_0.1.2_amd64.deb
sudo dpkg -i postgresql-9.1-tsearch-extras_0.1.2_amd64.deb

# If on 14.04:
wget https://launchpad.net/~tabbott/+archive/ubuntu/zulip/+files/postgresql-9.3-tsearch-extras_0.1.3_amd64.deb
sudo dpkg -i postgresql-9.3-tsearch-extras_0.1.3_amd64.deb

# If on 15.04 or jessie:
wget https://dl.dropboxusercontent.com/u/283158365/zuliposs/postgresql-9.4-tsearch-extras_0.1_amd64.deb
sudo dpkg -i postgresql-9.4-tsearch-extras_0.1_amd64.deb

# If on 16.04 or stretch
wget https://launchpad.net/~tabbott/+archive/ubuntu/zulip/+files/postgresql-9.5-tsearch-extras_0.2_amd64.deb
sudo dpkg -i postgresql-9.5-tsearch-extras_0.2_amd64.deb
```

Alternatively, you can always build the package from [tsearch-extras
git](https://github.com/zulip/tsearch_extras).

Now continue with the [All Systems](#all-systems) instructions below.

#### Using the [official Zulip PPA][zulip-ppa] (for 14.04 Trusty or 16.04 Xenial):

[zulip-ppa]: https://launchpad.net/~tabbott/+archive/ubuntu/zulip/+packages

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
sudo add-apt-repository ppa:tabbott/zulip
sudo apt-get update
sudo apt-get install closure-compiler libfreetype6-dev libffi-dev \
    memcached rabbitmq-server libldap2-dev redis-server \
    postgresql-server-dev-all libmemcached-dev python3-dev python-dev \
    hunspell-en-us nodejs nodejs-legacy git yui-compressor \
    puppet gettext tsearch-extras
```

Now continue with the [All Systems](#all-systems) instructions below.

### On Fedora 22 (experimental):

These instructions are experimental and may have bugs; patches
welcome!

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
sudo dnf install libffi-devel memcached rabbitmq-server \
    openldap-devel python-devel redis postgresql-server \
    postgresql-devel postgresql libmemcached-devel freetype-devel \
    nodejs yuicompressor closure-compiler gettext
```

Now continue with the [Common to Fedora/CentOS](#common-to-fedora-centos-instructions) instructions below.

### On CentOS 7 Core (experimental):

These instructions are experimental and may have bugs; patches
welcome!

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
# Add user zulip to the system (not necessary if you configured zulip
# as the administrator user during the install process of CentOS 7).
useradd zulip

# Create a password for zulip user
passwd zulip

# Allow zulip to sudo
visudo
# Add this line after line `root    ALL=(ALL)       ALL`
zulip   ALL=(ALL)       ALL

# Switch to zulip user
su zulip

# Enable EPEL 7 repo so we can install rabbitmq-server, redis and
# other dependencies
sudo yum install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm

# Install dependencies
sudo yum install libffi-devel memcached rabbitmq-server openldap-devel \
    python-devel redis postgresql-server postgresql-devel postgresql \
    libmemcached-devel wget python-pip openssl-devel freetype-devel \
    libjpeg-turbo-devel zlib-devel nodejs yuicompressor \
    closure-compiler gettext

# We need these packages to compile tsearch-extras
sudo yum groupinstall "Development Tools"

# clone Zulip's git repo and cd into it
cd && git clone https://github.com/zulip/zulip && cd zulip/

## NEEDS TESTING: The next few DB setup items may not be required at all.
# Initialize the postgres db
sudo postgresql-setup initdb

# Edit the postgres settings:
sudo vi /var/lib/pgsql/data/pg_hba.conf

# Change these lines:
host    all             all             127.0.0.1/32            ident
host    all             all             ::1/128                 ident
# to this:
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
```

Now continue with the [Common to Fedora/CentOS](#common-to-fedora-centos-instructions) instructions below.

### On OpenBSD 5.8 (experimental):

These instructions are experimental and may have bugs; patches
welcome!

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
doas pkg_add sudo bash gcc postgresql-server redis rabbitmq \
    memcached node libmemcached py-Pillow py-cryptography py-cffi

# Get tsearch_extras and build it (using a modified version which
# aliases int4 on OpenBSD):
git clone https://github.com/blablacio/tsearch_extras
cd tsearch_extras
gmake && sudo gmake install

# Point environment to custom include locations and use newer GCC
# (needed for Node modules):
export CFLAGS="-I/usr/local/include -I/usr/local/include/sasl"
export CXX=eg++

# Create tsearch_data directory:
sudo mkdir /usr/local/share/postgresql/tsearch_data


# Hack around missing dictionary files -- need to fix this to get the
# proper dictionaries from what in debian is the hunspell-en-us
# package.
sudo touch /usr/local/share/postgresql/tsearch_data/english.stop
sudo touch /usr/local/share/postgresql/tsearch_data/en_us.dict
sudo touch /usr/local/share/postgresql/tsearch_data/en_us.affix
```

Finally continue with the [All Systems](#all-systems) instructions below.

### Common to Fedora/CentOS instructions

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
# Build and install postgres tsearch-extras module
wget https://launchpad.net/~tabbott/+archive/ubuntu/zulip/+files/tsearch-extras_0.1.3.tar.gz
tar xvzf tsearch-extras_0.1.3.tar.gz
cd ts2
make
sudo make install

# Hack around missing dictionary files -- need to fix this to get the
# proper dictionaries from what in debian is the hunspell-en-us
# package.
sudo touch /usr/share/pgsql/tsearch_data/english.stop
sudo touch /usr/share/pgsql/tsearch_data/en_us.dict
sudo touch /usr/share/pgsql/tsearch_data/en_us.affix

# Edit the postgres settings:
sudo vi /var/lib/pgsql/data/pg_hba.conf

# Add this line before the first uncommented line to enable password
# auth:
host    all             all             127.0.0.1/32            md5

# Start the services
sudo systemctl start redis memcached rabbitmq-server postgresql

# Enable automatic service startup after the system startup
sudo systemctl enable redis rabbitmq-server memcached postgresql
```

Finally continue with the [All Systems](#all-systems) instructions below.

### All Systems:

Make sure you have followed the steps specific for your platform:

* [Debian or Ubuntu systems](#on-debian-or-ubuntu-systems)
* [Fedora 22 (experimental)](#on-fedora-22-experimental)
* [CentOS 7 Core (experimental)](#on-centos-7-core-experimental)
* [OpenBSD 5.8 (experimental)](#on-openbsd-5-8-experimental)
* [Fedora/CentOS](#common-to-fedora-centos-instructions)

For managing Zulip's python dependencies, we recommend using
[virtualenvs](https://virtualenv.pypa.io/en/stable/).

You must create a Python 3 virtualenv.  You must also install appropriate
python packages in it.

You should either install the virtualenv in `/srv`, or put a symlink to it in
`/srv`.  If you don't do that, some scripts might not work correctly.

You can run `python3 tools/setup/setup_venvs.py`.  This script will create a
virtualenv `/srv/zulip-py3-venv`.

If you want to do it manually, here are the steps:

```
sudo virtualenv /srv/zulip-py3-venv -p python3 # Create a python3 virtualenv
sudo chown -R `whoami`:`whoami` /srv/zulip-py3-venv
source /srv/zulip-py3-venv/bin/activate # Activate python3 virtualenv
pip install --upgrade pip # upgrade pip itself because older versions have known issues
pip install --no-deps -r requirements/dev_lock.txt # install python packages required for development
```

Now run these commands:

```
sudo ./scripts/lib/install-node
yarn install
sudo mkdir /srv/zulip-emoji-cache
sudo chown -R `whoami`:`whoami` /srv/zulip-emoji-cache
./tools/setup/emoji/build_emoji
./tools/inline-email-css
./tools/setup/build_pygments_data.py
./tools/setup/generate_zulip_bots_static_files
./scripts/setup/generate_secrets.py --development
if [ $(uname) = "OpenBSD" ]; then
    sudo cp ./puppet/zulip/files/postgresql/zulip_english.stop /var/postgresql/tsearch_data/
else
    sudo cp ./puppet/zulip/files/postgresql/zulip_english.stop /usr/share/postgresql/9.*/tsearch_data/
fi
./scripts/setup/configure-rabbitmq
./tools/setup/postgres-init-dev-db
./tools/do-destroy-rebuild-database
./tools/setup/postgres-init-test-db
./tools/do-destroy-rebuild-test-database
./manage.py compilemessages
```

To start the development server:

```
./tools/run-dev.py
```

… and visit <http://localhost:9991/>.

#### Proxy setup for by-hand installation

If you are building the development environment on a network where a
proxy is required to access the Internet, you will need to set the
proxy in the environment as follows:

- On Ubuntu, set the proxy environment variables using:
 ```
 export https_proxy=http://proxy_host:port
 export http_proxy=http://proxy_host:port
 ```

- And set the yarn proxy and https-proxy using:
 ```
 yarn config set proxy http://proxy_host:port
 yarn config set https-proxy http://proxy_host:port
 ```

## Using Docker (experimental)

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
docker build -t user/zulipdev -f Dockerfile-dev .
```


Commit and tag the provisioned images. The below will install Zulip's dependencies:
```
docker run -itv $(pwd):/srv/zulip -p 9991:9991 user/zulipdev /bin/bash
$ /bin/bash sudo chown -R zulip:zulip /srv/zulip
$ /bin/bash /srv/zulip/tools/provision --docker
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
