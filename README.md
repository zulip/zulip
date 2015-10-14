Zulip
=====

Zulip is a powerful, open source group chat application. Written in
Python and using the Django framework, Zulip supports both private
messaging and group chats via conversation streams.

Zulip also supports fast search, drag-and-drop file uploads, image
previews, group private messages, audible notifications,
missed-message emails, desktop apps, and much more.

Further information on the Zulip project and its features can be found
at https://www.zulip.org

Contributing to Zulip
=====================

Zulip welcomes all forms of contributions!

Before a pull request can be merged, you need to to sign the [Dropbox
Contributor License Agreement](https://opensource.dropbox.com/cla/).

Please run the tests (tools/test-all) before submitting your pull
request and read our [commit message style
guidelines](http://zulip.readthedocs.org/en/latest/code-style.html#commit-messages).

Zulip has a growing collection of developer documentation including
detailed documentation on coding style available on [Read The
Docs](https://zulip.readthedocs.org/).

Zulip also has a [development discussion mailing list](https://groups.google.com/forum/#!forum/zulip-devel)

Feel free to send any questions or suggestions of areas where you'd
love to see more documentation to the list!

We recommend sending proposals for large features or refactorings to
the zulip-devel list for discussion and advice before getting too deep
into implementation.

Please report any security issues you discover to support@zulip.com.

Running Zulip in production
===========================

This is documented in https://zulip.org/server.html and [README.prod.md](README.prod.md).

Installing the Zulip Development environment
============================================

You will need a machine with at least 2GB of RAM available (see
https://github.com/zulip/zulip/issues/32 for a plan for how to
dramatically reduce this requirement).

Start by cloning this repository: `git clone https://github.com/zulip/zulip.git`

Using Vagrant
-------------

This is the recommended approach, and is tested on OS X 10.10 as well as Ubuntu 14.04.

* The best performing way to run the Zulip development environment is
  using an LXC container.  If your host is Ubuntu 14.04 (or newer;
  what matters is having support for LXC containers), you'll want to
  install and configure the LXC Vagrant provider like this:
  `sudo apt-get install vagrant lxc lxc-templates cgroup-lite redir && vagrant plugin install vagrant-lxc`

* If your host is OS X, [download VirtualBox](https://www.virtualbox.org/wiki/Downloads),
  [download Vagrant](https://www.vagrantup.com/downloads.html), and install them both.

Once that's done, simply change to your zulip directory and run
`vagrant up` in your terminal to install the development server.  This
will take a long time on the first run because Vagrant needs to
download the Ubuntu Trusty base image, but later you can run `vagrant
destroy` and then `vagrant up` again to rebuild the environment and it
will be much faster.

Once that finishes, you can run the development server as follows:

```
vagrant ssh -- -L9991:localhost:9991
# Now inside the container
cd /srv/zulip
source /srv/zulip-venv/bin/activate
./tools/run-dev.py --interface=''
```

You can now visit <http://localhost:9991/> in your browser.  To get
shell access to the virtual machine running the server, use `vagrant ssh`.

(A small note on tools/run-dev.py: the `--interface=''` option will make
the development server listen on all network interfaces.  While this
is correct for the Vagrant guest sitting behind a NAT, you probably
don't want to use that option when using run-dev.py in other environments).

The run-dev.py console output will show any errors your Zulip
development server encounters.  It runs on top of Django's "manage.py
runserver" tool, which will automatically restart the Zulip server
whenever you save changes to Python code.

However, the Zulip queue workers will not automatically restart when
you save changes, so you will need to ctrl-C and then restart
`run-dev.py` manually if you are testing changes to the queue workers
or if a queue worker has crashed.

Using provision.py without Vagrant
----------------------------------

If you'd like to install a Zulip development environment on a server
that's already running Ubuntu 14.04 Trusty, you can do that by just
running:

```
sudo apt-get update
sudo apt-get install -y python-pbs
python /srv/zulip/provision.py

cd /srv/zulip
source /srv/zulip-venv/bin/activate
./tools/run-dev.py
```

By hand
-------
If you really want to install everything by hand, the below
instructions should work.

Install the following non-Python dependencies:
 * libffi-dev — needed for some Python extensions
 * postgresql 9.1 or later — our database (also install development headers)
 * memcached (and headers)
 * rabbitmq-server
 * libldap2-dev
 * python-dev
 * redis-server — rate limiting
 * tsearch-extras — better text search
 * libfreetype6-dev - needed before you pip install Pillow to properly generate emoji PNGs

On Debian or Ubuntu systems:

```
sudo apt-get install libffi-dev memcached rabbitmq-server libldap2-dev python-dev redis-server postgresql-server-dev-all libmemcached-dev libfreetype6-dev

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

Now continue with the "All systems" instructions below.

On Fedora 22 (experimental):

```
sudo dnf install libffi-devel memcached rabbitmq-server openldap-devel python-devel redis postgresql-server postgresql-devel postgresql libmemcached-devel freetype-devel
wget https://launchpad.net/~tabbott/+archive/ubuntu/zulip/+files/tsearch-extras_0.1.3.tar.gz
tar xvzf tsearch-extras_0.1.3.tar.gz
cd ts2
make
sudo make install

# Hack around missing dictionary files -- need to fix this to get
# the proper dictionaries from what in debian is the hunspell-en-us package.
sudo touch /usr/share/pgsql/tsearch_data/english.stop
sudo touch /usr/share/pgsql/tsearch_data/en_us.dict
sudo touch /usr/share/pgsql/tsearch_data/en_us.affix

# Edit the postgres settings:
sudo vi /var/lib/pgsql/data/pg_hba.conf

# Add this line before the first uncommented line to enable password auth:
host    all             all             127.0.0.1/32            md5

# Start the services
sudo systemctl start redis memcached rabbitmq-server postgresql
```

All Systems:

```
pip install -r requirements.txt
./tools/download-zxcvbn
./tools/emoji_dump/build_emoji
./scripts/setup/generate_secrets.py -d
sudo cp ./puppet/zulip/files/postgresql/zulip_english.stop /usr/share/postgresql/9.3/tsearch_data/
./scripts/setup/configure-rabbitmq
./tools/postgres-init-db
./tools/do-destroy-rebuild-database
./tools/postgres-init-test-db
./tools/do-destroy-rebuild-test-database
```

To start the development server:

```
./tools/run-dev.py
```

… and visit [http://localhost:9991/](http://localhost:9991/).


Running the test suite
======================

Run all tests:

```
./tools/test-all
```

This runs the linter plus all of our test suites; they can all be run
separately (just read `tools/test-all` to see them).  You can also run
individual tests, e.g.:

```
./tools/test-backend zerver.test_bugdown.BugdownTest.test_inline_youtube
./tools/test-js-with-casper 10-navigation.js
```

The above instructions include the first-time setup of test databases,
but you may need to rebuild the test database occasionally if you're
working on new database migrations.  To do this, run:

```
./tools/postgres-init-test-db
./tools/do-destroy-rebuild-test-database
```

Possible testing issues
=======================

- The Casper tests are flaky on the Virtualbox environment (probably
  due to some performance-sensitive races; they work reliably in
  Travis CI).  Until this issue is debugged, you may need to rerun
  them to get them to pass.

- When running the test suite, if you get an error like this:

  ```
      sqlalchemy.exc.ProgrammingError: (ProgrammingError) function ts_match_locs_array(unknown, text, tsquery) does not   exist
      LINE 2: ...ECT message_id, flags, subject, rendered_content, ts_match_l...
                                                                   ^
  ```

  … then you need to install tsearch-extras, described
  above. Afterwards, re-run the `init*-db` and the
  `do-destroy-rebuild*-database` scripts.

- When building the development environment using Vagrant and the LXC provider, if you encounter permissions errors, you may need to `chown -R 1000:$(whoami) /path/to/zulip` on the host before running `vagrant up` in order to ensure that the synced directory has the correct owner during provision. This issue will arise if you run `id username` on the host where `username` is the user running Vagrant and the output is anything but 1000.
  This seems to be caused by Vagrant behavior; more information can be found here https://github.com/fgrehm/vagrant-lxc/wiki/FAQ#help-my-shared-folders-have-the-wrong-owner

License
=======

Copyright 2011-2015 Dropbox, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

The software includes some works released by third parties under other
free and open source licenses. Those works are redistributed under the
license terms under which the works were received. For more details,
see the ``THIRDPARTY`` file included with this distribution.
