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

This section details some basic guidelines on for running a Zulip
server for larger organizations (especially >1000 users or 500+ daily
active users).  Zulip's resource needs depend roughly on 3 parameters:
daily active users (e.g. number of employees if everyone's an
employee), total user accounts (can be much larger), and message
volume.

In the following, we discuss a configuration with at most two types of
servers: application servers (running Django, Tornado, RabbitMQ,
Redis, Memcached, etc.) and database servers.  Of the application
server services, Django dominates the resource requirements.  One can
run every service on its own system (as
[docker-zulip](https://github.com/zulip/docker-zulip) does) but for
most use cases, there's little scalability benefit to doing so.  See
[deployment options](../production/deployment.md) for details on
installing Zulip with a dedicated database server.

* **Dedicated database**.  For installations with hundreds of daily
  active users, we recommend using a [remote postgres
  database](postgres.md), but it's not required.

* **RAM:**  We recommended more RAM for larger installations:
    * With 25+ daily active users, 4GB of RAM (Under that, Zulip runs
      its queue processors in a special low-resource mode).
    * With 100+ daily active users, 8GB of RAM.
    * With 400+ daily active users, 16GB of RAM for the Zulip
      application server, plus 16GB for the database.
    * With 2000+ daily active users 32GB of RAM, plus 32GB for the
      database.
    * Roughly linear scaling beyond that.

* **CPU:**  The Zulip application server's CPU usage is heavily
  optimized due to extensive work on optimizing the performance of
  requests for latency reasons.  Because most servers with sufficient
  RAM have sufficient CPU resources, CPU requirements are rarely an
  issue.  For larger installations with a dedicated database, we
  recommend high-CPU instances for the application server and a
  database-optimized (usually low CPU, high memory) instance for the
  database.

* **Disk for application server:** We recommend using [the S3 file
  uploads backend][s3-uploads] to store uploaded files at scale.  With
  that configuration, we recommend 50GB of disk for the OS, Zulip
  software, logs and scratch/free space.

* **Disk for database:** SSD disk is highly recommended.  For
  installations where most messages have <100 recipients, 10GB per 1M
  messages of history is sufficient plus 1GB per 1000 users is
  sufficient.  If most messages are to public streams with 10K+ users
  subscribed (like on chat.zulip.org), add 20GB per (1000 user
  accounts) per (1M messages to public streams).

* **Example:**  When the
  [chat.zulip.org](../contributing/chat-zulip-org.md) community server
  has 12K user accounts (~300 hundred daily actives) and 800K messages
  of history (400K to public streams), it had 16GB of RAM, 4 cores, and
  its database was using 100GB of disk.  It is a default
  configuration single-server installation.  The CPUs are essentially
  always idle.

* **Disaster recovery:** One can easily run a hot spare application
  server and a hot spare database (using [Postgres streaming
  replication][streaming-replication]).  Make sure the hot spare
  application server has copies of `/etc/zulip` and you're either
  syncing `LOCAL_UPLOADS_DIR` or using the [S3 file uploads
  backend][s3-uploads].

* **Sharding:** Zulip releases do not fully support dividing Tornado
  traffic for a single Zulip realm/organization between multiple
  application servers, which is why we recommend a hot spare over
  load-balancing.  We don't have an easily deployed configuration for
  load-balancing Tornado within a single organization, and as a result
  can't currently offer this model outside of enterprise support
  contracts.

* Zulip 2.0 and later supports running multiple Tornado servers
  sharded by realm/organization, which is how we scale Zulip Cloud.
  Contact us for help implementing the sharding policy.

Scalability is an area of active development, so if you're unsure
whether Zulip is a fit for your organization or need further advice
[contact Zulip support](mailto:support@zulipchat.com).

[s3-uploads]: ../production/upload-backends.html#s3-backend-configuration
[streaming-replication]: ../production/export-and-import.html#postgres-streaming-replication
