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
