
Installing the Zulip Development environment
============================================

* [Development environment setup for first-time
  contributors](#development-environment-setup-for-first-time-contributors)
* [Brief installation instructions for Vagrant development
  environment](#brief-installation-instructions-for-vagrant-development-environment)
* [Installing on Ubuntu 14.04 Trusty without
  Vagrant](#installing-on-ubuntu-1404-trusty-without-vagrant) (possibly more
  convenient but more work to maintain/uninstall)
* [Installing manually on UNIX-based
  platforms](#installing-manually-on-unix-based-platforms)
* [Using Docker (experimental)](#using-docker-experimental)
* [Using the Development Environment](#using-the-development-environment)
* [Running the test suite](#running-the-test-suite)

Those who have installed Zulip before or are experienced at administering Linux
may wish to skip ahead to [Brief installation instructions for Vagrant
development environment](#brief-installation-instructions-for-vagrant-development-environment),
[Using Docker (experimental)](#using-docker-experimental), or [Installing
manually on UNIX-based platforms](#installing-manually-on-unix-based-platforms).

## Development environment setup for first-time contributors

See [the setup
guide](https://zulip.readthedocs.org/en/latest/dev-env-first-time-contributors.html).

Brief installation instructions for Vagrant development environment
-------------

See [the Vagrant guide](https://zulip.readthedocs.org/en/latest/brief-install-vagrant-dev.html).

Installing on Ubuntu 14.04 Trusty without Vagrant
----------------------------------
Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

If you'd like to install a Zulip development environment on a server
that's already running Ubuntu 14.04 Trusty, you can do that by just
running:

```
sudo apt-get update
python /srv/zulip/tools/provision.py

cd /srv/zulip
source /srv/zulip-venv/bin/activate
./tools/run-dev.py
```

Note that there is no supported uninstallation process without Vagrant
(with Vagrant, you can just do `vagrant destroy` to clean up the
development environment).

Installing manually on UNIX-based platforms
-------

* [Debian or Ubuntu systems](#on-debian-or-ubuntu-systems)
* [Fedora 22 (experimental)](#on-fedora-22-experimental)
* [CentOS 7 Core (experimental)](#on-centos-7-core-experimental)
* [OpenBSD 5.8 (experimental)](#on-openbsd-58-experimental)
* [Fedora/CentOS](#common-to-fedoracentos-instructions)
* [Steps for all systems](#all-systems)

If you really want to install everything manually, the below instructions
should work.

Install the following non-Python dependencies:
 * libffi-dev — needed for some Python extensions
 * postgresql 9.1 or later — our database (client, server, headers)
 * nodejs 0.10 (and npm)
 * memcached (and headers)
 * rabbitmq-server
 * libldap2-dev
 * python-dev
 * redis-server — rate limiting
 * tsearch-extras — better text search
 * libfreetype6-dev — needed before you pip install Pillow to properly generate emoji PNGs

### On Debian or Ubuntu systems:

#### Using the official Ubuntu repositories and `tsearch-extras` deb package:

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
sudo apt-get install closure-compiler libfreetype6-dev libffi-dev \
    memcached rabbitmq-server libldap2-dev redis-server \
    postgresql-server-dev-all libmemcached-dev python-dev \
    hunspell-en-us nodejs nodejs-legacy npm git yui-compressor \
    puppet gettext

# If on 12.04 or wheezy:
sudo apt-get install postgresql-9.1
wget https://dl.dropboxusercontent.com/u/283158365/zuliposs/postgresql-9.1-tsearch-extras_0.1.2_amd64.deb
sudo dpkg -i postgresql-9.1-tsearch-extras_0.1.2_amd64.deb

# If on 14.04:
sudo apt-get install postgresql-9.3
wget https://dl.dropboxusercontent.com/u/283158365/zuliposs/postgresql-9.3-tsearch-extras_0.1.2_amd64.deb
sudo dpkg -i postgresql-9.3-tsearch-extras_0.1.2_amd64.deb

# If on 15.04 or jessie:
sudo apt-get install postgresql-9.4
wget https://dl.dropboxusercontent.com/u/283158365/zuliposs/postgresql-9.4-tsearch-extras_0.1_amd64.deb
sudo dpkg -i postgresql-9.4-tsearch-extras_0.1_amd64.deb
```

Now continue with the [All Systems](#all-systems) instructions below.

#### Using the [official Zulip PPA](https://launchpad.net/~tabbott/+archive/ubuntu/zulip/+packages) (for 14.04 Trusty):

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

```
sudo add-apt-repository ppa:tabbott/zulip
sudo apt-get update
sudo apt-get install closure-compiler libfreetype6-dev libffi-dev \
    memcached rabbitmq-server libldap2-dev redis-server \
    postgresql-server-dev-all libmemcached-dev python-dev \
    hunspell-en-us nodejs nodejs-legacy npm git yui-compressor \
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
    nodejs npm yuicompressor closure-compiler gettext
```

Finally continue with the [All Systems](#all-systems) instructions below.

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

Now continue with the [Common to Fedora/CentOS](#common-to-fedoracentos-instructions) instructions below.

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
* [OpenBSD 5.8 (experimental)](#on-openbsd-58-experimental)
* [Fedora/CentOS](#common-to-fedoracentos-instructions)

For managing Zulip's python dependencies, we recommend using a
[virtualenv](https://virtualenv.pypa.io/en/stable/).

Once you have created and activated a virtualenv, do the following:

```
pip install --upgrade pip # upgrade pip itself because older versions have known issues.
pip install --no-deps -r requirements/py2_dev.txt # install python packages required for development
./tools/setup/install-phantomjs
./tools/install-mypy
./tools/setup/download-zxcvbn
./tools/setup/emoji_dump/build_emoji
./scripts/setup/generate_secrets.py -d
if [ $(uname) = "OpenBSD" ]; then sudo cp ./puppet/zulip/files/postgresql/zulip_english.stop /var/postgresql/tsearch_data/; else sudo cp ./puppet/zulip/files/postgresql/zulip_english.stop /usr/share/postgresql/9.*/tsearch_data/; fi
./scripts/setup/configure-rabbitmq
./tools/setup/postgres-init-dev-db
./tools/do-destroy-rebuild-database
./tools/setup/postgres-init-test-db
./tools/do-destroy-rebuild-test-database
./manage.py compilemessages
npm install
```

If `npm install` fails, the issue may be that you need a newer version
of `npm`.  You can use `npm install -g npm` to update your version of
`npm` and try again.

To start the development server:

```
./tools/run-dev.py
```

… and visit [http://localhost:9991/](http://localhost:9991/).

#### Proxy setup for by-hand installation

If you are building the development environment on a network where a
proxy is required to access the Internet, you will need to set the
proxy in the environment as follows:

- On Ubuntu, set the proxy environment variables using:
 ```
 export https_proxy=http://proxy_host:port
 export http_proxy=http://proxy_host:port
 ```

- And set the npm proxy and https-proxy using:
 ```
 npm config set proxy http://proxy_host:port
 npm config set https-proxy http://proxy_host:port
 ```

Using Docker (experimental)
---------------------------
See [the Docker instructions](https://zulip.readthedocs.io/en/latest/install-docker-dev.html).

[using-dev]: https://zulip.readthedocs.io/en/latest/using-dev-environment.html


Using the Development Environment
=================================

See [this guide](https://zulip.readthedocs.io/en/latest/using-dev-environment.html).

[django-runserver]: https://docs.djangoproject.com/en/1.8/ref/django-admin/#runserver-port-or-address-port
[new-feature-tutorial]: http://zulip.readthedocs.io/en/latest/new-feature-tutorial.html
[testing-docs]: http://zulip.readthedocs.io/en/latest/testing.html

[dev-install]: http://zulip.readthedocs.io/en/latest/dev-install-choices.html
[vagrant-dl]: https://www.vagrantup.com/downloads.html
[vagrant-lxc]: https://github.com/fgrehm/vagrant-lxc
[vbox-dl]: https://www.virtualbox.org/wiki/Downloads
[avoiding-sudo]: https://github.com/fgrehm/vagrant-lxc#avoiding-sudo-passwords

Running the test suite
======================

See [the developer testing
guide)[https://zulip.readthedocs.org/en/latest/test-suite-dev.html).
