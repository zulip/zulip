
Installing the Zulip Development environment

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
See [this guide](https://zulip.readthedocs.io/en/latest/install-ubuntu-without-vagrant-dev.html).

Installing manually on UNIX-based platforms
-------

See [this guide](https://zulip.readthedocs.io/en/latest/install-generic-unix-dev.html).

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
The Zulip development environment is the recommended option for folks
interested in trying out Zulip.  This is documented in [the developer
installation guide][dev-install].

[dev-install]: http://zulip.readthedocs.io/en/latest/dev-install-choices.html
[vagrant-dl]: https://www.vagrantup.com/downloads.html
[vagrant-lxc]: https://github.com/fgrehm/vagrant-lxc
[vbox-dl]: https://www.virtualbox.org/wiki/Downloads
[avoiding-sudo]: https://github.com/fgrehm/vagrant-lxc#avoiding-sudo-passwords

Running the test suite
======================

See [the developer testing guide](https://zulip.readthedocs.org/en/latest/testing.html).
