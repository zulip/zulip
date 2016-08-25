# Installing directly on Ubuntu

Start by cloning this repository: `git clone
https://github.com/zulip/zulip.git`

If you'd like to install a Zulip development environment on a computer
that's already running Ubuntu 14.04 Trusty or Ubuntu 16.04 Xenial, you
can do that by just running:

```
# From a clone of zulip.git
./tools/provision.py
source /srv/zulip-venv/bin/activate
./tools/run-dev.py  # starts the development server
```

Note that there is no supported uninstallation process without Vagrant
(with Vagrant, you can just do `vagrant destroy` to clean up the
development environment).

Once you've done the above setup, you can pick up the [documentation
on using the Zulip development
environment](dev-env-first-time-contributors.html#step-4-developing),
ignoring the parts about `vagrant` (since you're not using it).
