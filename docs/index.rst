.. zulip documentation master file, created by
   sphinx-quickstart on Mon Aug 17 16:24:04 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Zulip documentation!
===============================

Zulip is a powerful, open source group chat application. Written in
Python and using the Django framework, Zulip supports both private
messaging and group chats via conversation streams.

Zulip also supports fast search, drag-and-drop file uploads, image
previews, group private messages, audible notifications, missed-message
emails, desktop apps, and much more.

Further information on the Zulip project and its features can be found
at `https://www.zulip.org <https://www.zulip.org>`__ and in these
docs.  Our code is available at `our GitHub repository
<https://github.com/zulip/>`__.

This set of documents covers installation and contribution instructions.

Contents:

* :ref:`user-docs`
* :ref:`prod-install-docs`
* :ref:`dev-install-docs`
* :ref:`tutorial-docs`
* :ref:`code-docs`
* :ref:`system-docs`

.. _user-docs:

.. toctree::
   :maxdepth: 2
   :caption: Overview

   readme-symlink
   architecture-overview
   directory-structure
   roadmap
   changelog

.. _prod-install-docs:

.. toctree::
   :maxdepth: 2
   :caption: Zulip in production

   prod-requirements
   prod-install
   prod-troubleshooting
   prod-customize
   prod-maintain-secure-upgrade
   prod-authentication-methods
   prod-postgres

.. _dev-install-docs:

.. toctree::
   :maxdepth: 2
   :caption: Installation for developers

   dev-overview
   dev-env-first-time-contributors
   brief-install-vagrant-dev
   install-ubuntu-without-vagrant-dev
   install-generic-unix-dev
   install-docker-dev
   using-dev-environment

.. _tutorial-docs:

.. toctree::
   :maxdepth: 2
   :caption: Developer tutorials

   integration-guide
   new-feature-tutorial
   writing-views
   life-of-a-request

.. _code-docs:

.. toctree::
   :maxdepth: 2
   :caption: Code contribution guide

   version-control
   code-style
   testing
   mypy

.. _system-docs:

.. toctree::
   :maxdepth: 2
   :caption: Subsystem documentation

   settings
   queuing
   pointer
   markdown
   front-end-build-process
   schema-migrations
   html_css
   full-text-search
   translating
   logging
   README

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

