apt
===

[![Build Status](https://travis-ci.org/puppetlabs/puppetlabs-apt.png?branch=master)](https://travis-ci.org/puppetlabs/puppetlabs-apt)

## Description
Provides helpful definitions for dealing with Apt.
=======
Overview
--------

The APT module provides a simple interface for managing APT source, key, and definitions with Puppet. 

Module Description
------------------

APT automates obtaining and installing software packages on *nix systems. 

Setup
-----

**What APT affects:**

* package/service/configuration files for APT 
* your system's `sources.list` file and `sources.list.d` directory
    * NOTE: Setting the `purge_sources_list` and `purge_sources_list_d` parameters to 'true' will destroy any existing content that was not declared with Puppet. The default for these parameters is 'false'.
* system repositories
* authentication keys
* wget (optional)

###Beginning with APT

To begin using the APT module with default parameters, declare the class

    class { 'apt': }
 
Puppet code that uses anything from the APT module requires that the core apt class be declared. 

Usage
-----

Using the APT module consists predominantly in declaring classes that provide desired functionality and features. 
 
###apt

`apt` provides a number of common resources and options that are shared by the various defined types in this module, so you MUST always include this class in your manifests.

The parameters for `apt` are not required in general and are predominantly for development environment use-cases.

    class { 'apt':
      always_apt_update    => false,
      disable_keys         => undef,
      proxy_host           => false,
      proxy_port           => '8080',
      purge_sources_list   => false,
      purge_sources_list_d => false,
      purge_preferences_d  => false,
      update_timeout       => undef
    }

Puppet will manage your system's `sources.list` file and `sources.list.d` directory but will do its best to respect existing content. 

If you declare your apt class with `purge_sources_list` and `purge_sources_list_d` set to 'true', Puppet will unapologetically purge any existing content it finds that wasn't declared with Puppet. 

###apt::builddep

Installs the build depends of a specified package.

    apt::builddep { 'glusterfs-server': }

###apt::force

Forces a package to be installed from a specific release.  This class is particularly useful when using repositories, like Debian, that are unstable in Ubuntu.

    apt::force { 'glusterfs-server':
	  release => 'unstable',
	  version => '3.0.3',
	  require => Apt::Source['debian_unstable'],
    }

###apt::key

Adds a key to the list of keys used by APT to authenticate packages.

    apt::key { 'puppetlabs':
      key        => '4BD6EC30',
      key_server => 'pgp.mit.edu',
    }

    apt::key { 'jenkins':
      key        => 'D50582E6',
      key_source => 'http://pkg.jenkins-ci.org/debian/jenkins-ci.org.key',
    }

Note that use of `key_source` requires wget to be installed and working.

###apt::pin

Adds an apt pin for a certain release.

    apt::pin { 'karmic': priority => 700 }
    apt::pin { 'karmic-updates': priority => 700 }
    apt::pin { 'karmic-security': priority => 700 }

Note you can also specifying more complex pins using distribution properties.

    apt::pin { 'stable':
      priority        => -10,
      originator      => 'Debian',
      release_version => '3.0',
      component       => 'main',
      label           => 'Debian'
    }

###apt::ppa

Adds a ppa repository using `add-apt-repository`.

    apt::ppa { 'ppa:drizzle-developers/ppa': }

###apt::release

Sets the default apt release. This class is particularly useful when using repositories, like Debian, that are unstable in Ubuntu.

    class { 'apt::release':
      release_id => 'precise',
    }

###apt::source

Adds an apt source to `/etc/apt/sources.list.d/`.

    apt::source { 'debian_unstable':
      location          => 'http://debian.mirror.iweb.ca/debian/',
      release           => 'unstable',
      repos             => 'main contrib non-free',
      required_packages => 'debian-keyring debian-archive-keyring',
      key               => '55BE302B',
      key_server        => 'subkeys.pgp.net',
      pin               => '-10',
      include_src       => true
    }

If you would like to configure your system so the source is the Puppet Labs APT repository

    apt::source { 'puppetlabs':
      location   => 'http://apt.puppetlabs.com',
      repos      => 'main',
      key        => '4BD6EC30',
      key_server => 'pgp.mit.edu',
    }

###Testing

The APT module is mostly a collection of defined resource types, which provide reusable logic that can be leveraged to manage APT. It does provide smoke tests for testing functionality on a target system, as well as spec tests for checking a compiled catalog against an expected set of resources.

####Example Test

This test will set up a Puppet Labs apt repository. Start by creating a new smoke test in the apt module's test folder. Call it puppetlabs-apt.pp. Inside, declare a single resource representing the Puppet Labs APT source and gpg key

    apt::source { 'puppetlabs':
      location   => 'http://apt.puppetlabs.com',
      repos      => 'main',
      key        => '4BD6EC30',
      key_server => 'pgp.mit.edu',
    }
    
This resource creates an apt source named puppetlabs and gives Puppet information about the repository's location and key used to sign its packages. Puppet leverages Facter to determine the appropriate release, but you can set it directly by adding the release type.

Check your smoke test for syntax errors

    $ puppet parser validate tests/puppetlabs-apt.pp

If you receive no output from that command, it means nothing is wrong. Then apply the code

    $ puppet apply --verbose tests/puppetlabs-apt.pp
    notice: /Stage[main]//Apt::Source[puppetlabs]/File[puppetlabs.list]/ensure: defined content as '{md5}3be1da4923fb910f1102a233b77e982e'
    info: /Stage[main]//Apt::Source[puppetlabs]/File[puppetlabs.list]: Scheduling refresh of Exec[puppetlabs apt update]
    notice: /Stage[main]//Apt::Source[puppetlabs]/Exec[puppetlabs apt update]: Triggered 'refresh' from 1 events>

The above example used a smoke test to easily lay out a resource declaration and apply it on your system. In production, you may want to declare your APT sources inside the classes where they’re needed. 

Implementation
--------------

###apt::backports

Adds the necessary components to get backports for Ubuntu and Debian. The release name defaults to `$lsbdistcodename`. Setting this manually can cause undefined behavior (read: universe exploding).

Limitations
-----------

This module should work across all versions of Debian/Ubuntu and support all major APT repository management features. 

Development
------------

Puppet Labs modules on the Puppet Forge are open projects, and community contributions are essential for keeping them great. We can’t access the huge number of platforms and myriad of hardware, software, and deployment configurations that Puppet is intended to serve.

We want to keep it as easy as possible to contribute changes so that our modules work in your environment. There are a few guidelines that we need contributors to follow so that we can have a chance of keeping on top of things.

You can read the complete module contribution guide [on the Puppet Labs wiki.](http://projects.puppetlabs.com/projects/module-site/wiki/Module_contributing)

Contributors
------------

A lot of great people have contributed to this module. A somewhat current list follows:

* Ben Godfrey <ben.godfrey@wonga.com>
* Branan Purvine-Riley <branan@puppetlabs.com>
* Christian G. Warden <cwarden@xerus.org>  
* Dan Bode <bodepd@gmail.com> <dan@puppetlabs.com>  
* Garrett Honeycutt <github@garretthoneycutt.com>  
* Jeff Wallace <jeff@evolvingweb.ca> <jeff@tjwallace.ca>  
* Ken Barber <ken@bob.sh>  
* Matthaus Litteken <matthaus@puppetlabs.com> <mlitteken@gmail.com>  
* Matthias Pigulla <mp@webfactory.de>  
* Monty Taylor <mordred@inaugust.com>  
* Peter Drake <pdrake@allplayers.com>  
* Reid Vandewiele <marut@cat.pdx.edu>  
* Robert Navarro <rnavarro@phiivo.com>  
* Ryan Coleman <ryan@puppetlabs.com>  
* Scott McLeod <scott.mcleod@theice.com>  
* Spencer Krum <spencer@puppetlabs.com>  
* William Van Hevelingen <blkperl@cat.pdx.edu> <wvan13@gmail.com>  
* Zach Leslie <zach@puppetlabs.com>  
