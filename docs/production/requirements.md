# Requirements and Scalability

To run a Zulip server, you will need:
* A dedicated machine or VM
* A supported OS:
  * Ubuntu 18.04 Bionic
  * Ubuntu 16.04 Xenial
  * Debian 9 Stretch
  * Debian 10 Buster
* At least 2GB RAM, and 10GB disk space
  * If you expect 100+ users: 4GB RAM, and 2 CPUs
* A hostname in DNS
* Credentials for sending email

For details on each of these requirements, see below.

## Server

#### General

The installer expects Zulip to be the **only thing** running on the
system; it will install system packages with `apt` (like nginx,
postgresql, and redis) and configure them for its own use.  We
strongly recommend using either a fresh machine instance in a cloud
provider, a fresh VM, or a dedicated machine.  If you decide to
disregard our advice and use a server that hosts other services, we
can't support you, but
[we do have some notes on issues you'll encounter](install-existing-server.md).

#### Operating System

Ubuntu 18.04 Bionic, Ubuntu 16.04 Xenial, Debian Buster and Debian
Stretch are supported for running Zulip in production.  64-bit is
recommended.  We also recommend installing on the newest option you're
comfortable with, to save your organization the work of upgrading
(Ubuntu Trusty [reached end of life in April 2019][trusty-eol]; Zulip
2.0 was the last major release to support it).

If you're using Ubuntu, the
[Ubuntu universe repository][ubuntu-repositories] must be
[enabled][enable-universe], which is usually just:

```
sudo add-apt-repository universe
sudo apt update
```

[ubuntu-repositories]:
https://help.ubuntu.com/community/Repositories/Ubuntu
[enable-universe]: https://help.ubuntu.com/community/Repositories/CommandLine#Adding_the_Universe_and_Multiverse_Repositories

#### Hardware Specifications

* CPU and Memory: For installations with 100+ users you'll need a
  minimum of **2 CPUs** and **4GB RAM**. For installations with fewer
  users, 1 CPU and 2GB RAM is sufficient. We strongly recommend against
  installing with less than 2GB of RAM, as you will likely experience
  out of memory issues installing dependencies.  We recommend against
  using highly CPU-limited servers like the AWS `t2` style instances
  for organizations with a hundreds of users (active or no).

  See our
  [documentation on scalability](#scalability)
  for advice on hardware requirements for larger organizations.

* Disk space: You'll need at least 10GB of free disk space for a
  server with dozens of users. If you intend to store uploaded files
  locally rather than on S3 you will likely need more, depending how
  often your users upload large files.  You'll eventually need 100GB
  or more if you have thousands of active users or millions of total
  messages sent.  We recommend using an SSD and avoiding cloud storage
  backends that limit the IOPS per second, since the disk is primarily
  used for the database (assuming you're using the
  [S3 file uploads backend](../production/upload-backends.md)).

#### Network and Security Specifications

* Incoming HTTPS access (usually port 443, though this is
  [configurable](../production/deployment.html#using-an-alternate-port))
  from the networks where your users are (usually, the public
  Internet).  If you also open port 80, Zulip will redirect users to
  HTTPS rather than not working when users type
  e.g. `http://zulip.example.com` in their browser.  If you are using
  Zulip's [incoming email integration][email-mirror-code] you may also
  need incoming port 25 open.

[email-mirror-code]: https://github.com/zulip/zulip/blob/master/zerver/management/commands/email_mirror.py

* Outgoing HTTP(S) access (ports 80 and 443) to the public Internet so
  that Zulip can properly manage inline image previews.  You'll also
  need outgoing SMTP access to your SMTP server (the standard port for
  this is 587) so that Zulip can send email.

#### Domain name

You should already have a domain name (e.g., `zulip.example.com`)
available for your Zulip server. In order to generate valid SSL
certificates [with Certbot][doc-certbot], and to enable other services
such as Google authentication, you'll need to set the domain's
A record to point to your production server.

## Credentials needed

#### SSL Certificate

Your Zulip server will need an SSL certificate for the domain name it
uses.  For most Zulip servers, the recommended (and simplest) way to
get this is to just [use the `--certbot` option][doc-certbot] in the
Zulip installer, which will automatically get a certificate for you
and keep it renewed.

For test installations, an even simpler alternative is always
available: [the `--self-signed-cert` option][doc-self-signed] in the
installer.

If you'd rather acquire an SSL certificate another way, see our [SSL
certificate documentation](ssl-certificates.md).

[doc-certbot]: ssl-certificates.html#certbot-recommended
[doc-self-signed]: ssl-certificates.html#self-signed-certificate

#### Outgoing email

* Outgoing email (SMTP) credentials that Zulip can use to send
  outgoing emails to users (e.g. email address confirmation emails
  during the signup process, missed message notifications, password
  reset, etc.).  If you don't have an existing outgoing SMTP solution,
  read about
  [free outgoing SMTP options and options for prototyping](email.html#free-outgoing-email-services).

Once you have met these requirements, see [full instructions for installing
Zulip in production](../production/install.md).

[trusty-eol]: https://wiki.ubuntu.com/Releases

## Scalability

This section attempts to address the considerations involved with
running Zulip with larger teams (especially >1000 users).

* For an organization with 100+ users, it's important to have more
  than 4GB of RAM on the system.  Zulip will install on a system with
  2GB of RAM, but with less than 3.5GB of RAM, it will run its
  [queue processors](../subsystems/queuing.md) multithreaded to conserve memory;
  this creates a significant performance bottleneck.

* [chat.zulip.org](../contributing/chat-zulip-org.md), with thousands of user
  accounts and thousands of messages sent every week, has 8GB of RAM,
  4 cores, and 80GB of disk.  The CPUs are essentially always idle,
  but the 8GB of RAM is important.

* We recommend using a [remote postgres
  database](postgres.md) for isolation, though it is
  not required.  In the following, we discuss a relatively simple
  configuration with two types of servers: application servers
  (running Django, Tornado, RabbitMQ, Redis, Memcached, etc.) and
  database servers.

* You can scale to a pretty large installation (O(~1000) concurrently
  active users using it to chat all day) with just a single reasonably
  large application server (e.g. AWS c3.2xlarge with 8 cores and 16GB
  of RAM) sitting mostly idle (<10% CPU used and only 4GB of the 16GB
  RAM actively in use).  You can probably get away with half that
  (e.g. c3.xlarge), but ~8GB of RAM is highly recommended at scale.
  Beyond a 1000 active users, you will eventually want to increase the
  memory cap in `memcached.conf` from the default 512MB to avoid high
  rates of memcached misses.

* For the database server, we highly recommend SSD disks, and RAM is
  the primary resource limitation.  We have not aggressively tested
  for the minimum resources required, but 8 cores with 30GB of RAM
  (e.g. AWS's m3.2xlarge) should suffice; you may be able to get away
  with less especially on the CPU side.  The database load per user is
  pretty optimized as long as `memcached` is working correctly.  This
  has not been tested, but from extrapolating the load profile, it
  should be possible to scale a Zulip installation to 10,000s of
  active users using a single large database server without doing
  anything complicated like sharding the database.

* For reasonably high availability, it's easy to run a hot spare
  application server and a hot spare database (using Postgres
  streaming replication; see the section on configuring this).  Be
  sure to check out the section on backups if you're hoping to run a
  spare application server; in particular you probably want to use the
  S3 backend for storing user-uploaded files and avatars and will want
  to make sure secrets are available on the hot spare.

* Zulip 2.0 and later supports running multiple Tornado servers
  sharded by realm/organization, which is how we scale Zulip Cloud.

* However, Zulip does not yet support dividing traffic for a single
  Zulip realm between multiple application servers.  There are two
  issues: you need to share the memcached/Redis/RabbitMQ instance
  (these should can be moved to a network service shared by multiple
  servers with a bit of configuration) and the Tornado event system
  for pushing to browsers currently has no mechanism for multiple
  frontend servers (or event processes) talking to each other.  One
  can probably get a factor of 10 in a single server's scalability by
  [supporting multiple tornado processes on a single server](https://github.com/zulip/zulip/issues/372),
  which is also likely the first part of any project to support
  exchanging events amongst multiple servers.  The work for changing
  this is pretty far along, though, and thus while not generally
  available yet, we can set it up for users with an enterprise support
  contract.

Questions, concerns, and bug reports about this area of Zulip are very
welcome!  This is an area we are hoping to improve.
