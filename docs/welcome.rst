========
Welcome!
========

This document will guide you through getting started on Zulip development.

Installation
============

You should clone the Zulip git repository onto a Linux or OS X machine.
Then follow the instructions in README.dev.

Running the development server
==============================

After installing, you will have a virtual machine serving a development Zulip instance.
To start it, simply run `vagrant up` and navigate to `http://localhost:9991/`__ in
your browser.  Behind the scenes, this is running `run-dev.py` via `supervisor`.

Viewing the server log
----------------------

Sometimes things go wrong when you change backend code.  The server logs are stored
in `/var/logs/supervisor/zulip-dev-stdout---supervisor-******.log`.

Restarting run-dev.py
---------------------

Most of the time, the server will refresh when you change underlying python
files or style sheets, but sometimes you might need to restart the server
(for example, if you have a syntax error or need to change the database schema).
To do so, use `sudo supervisorctl restart zulip-dev`.

Making changes
==============

.. attention::
   We need to determine our final development workflow

