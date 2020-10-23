# Requirements and scalability

To run a Zulip server, you will need:
* A dedicated machine or VM
* A supported OS:
  * Ubuntu 20.04 Focal
  * Ubuntu 18.04 Bionic
  * Debian 10 Buster
* At least 2GB RAM, and 10GB disk space
  * If you expect 100+ users: 4GB RAM, and 2 CPUs
* A hostname in DNS
* Credentials for sending email

For details on each of these requirements, see below.

## Server

#### General

The installer expects Zulip to be the **only thing** running on the
system; it will install system packages with `apt` (like Nginx,
PostgreSQL, and Redis) and configure them for its own use.  We
strongly recommend using either a fresh machine instance in a cloud
provider, a fresh VM, or a dedicated machine.  If you decide to
disregard our advice and use a server that hosts other services, we
can't support you, but
[we do have some notes on issues you'll encounter](install-existing-server.md).

#### Operating system

Ubuntu 20.04 Focal, 18.04 Bionic, and Debian 10 Buster are supported
for running Zulip in production.  64-bit is recommended.  We recommend
installing on the newest supported OS release you're comfortable with,
to save a bit of future work [upgrading the operating
system][upgrade-os].

If you're using Ubuntu, the
[Ubuntu universe repository][ubuntu-repositories] must be
[enabled][enable-universe], which is usually just:

```
sudo add-apt-repository universe
sudo apt update
```

[upgrade-os]: ../production/upgrade-or-modify.html#upgrading-the-operating-system
[ubuntu-repositories]:
https://help.ubuntu.com/community/Repositories/Ubuntu
[enable-universe]: https://help.ubuntu.com/community/Repositories/CommandLine#Adding_the_Universe_and_Multiverse_Repositories

#### Hardware specifications

* CPU and memory: For installations with 100+ users you'll need a
  minimum of **2 CPUs** and **4GB RAM**. For installations with fewer
  users, 1 CPU and 2GB RAM is sufficient. We strongly recommend against
  installing with less than 2GB of RAM, as you will likely experience
  out of memory issues installing dependencies.  We recommend against
  using highly CPU-limited servers like the AWS `t2` style instances
  for organizations with hundreds of users (active or no).

* Disk space: You'll need at least 10GB of free disk space for a
  server with dozens of users.  We recommend using an SSD and avoiding
  cloud storage backends that limit the IOPS per second, since the
  disk is primarily used for the Zulip database.

See our [documentation on scalability](#scalability) below for advice
on hardware requirements for larger organizations.

#### Network and security specifications

* Incoming HTTPS access (usually port 443, though this is
  [configurable](../production/deployment.html#using-an-alternate-port))
  from the networks where your users are (usually, the public
  Internet).
* Incoming port 80 access (optional).  Zulip only serves content over
  HTTPS, and will redirect HTTP requests to HTTPS.
* Incoming port 25 if you plan to enable Zulip's [incoming email
  integration](../production/email-gateway.md).
* Outgoing HTTP(S) access (ports 80 and 443) to the public Internet so
  that Zulip can properly manage image previews and embeds.  Outgoing
  Internet access is not required if you [disable those
  features](https://zulip.com/help/allow-image-link-previews).
* Outgoing SMTP access (usually port 587) to your [SMTP
  server](../production/email.md) so that Zulip can send emails.
* A domain name (e.g. `zulip.example.com`) that your users will use to
  access the Zulip server.  In order to generate valid SSL
  certificates [with Certbot][doc-certbot], and to enable other
  services such as Google authentication, public DNS name is simpler,
  but Zulip can be configured to use a non-public domain or even an IP
  address as its external hostname (though we don't recommend that
  configuration).
* Zulip supports [running behind a reverse proxy][reverse-proxy].

[reverse-proxy]: ../production/deployment.html#putting-the-zulip-application-behind-a-reverse-proxy
[email-mirror-code]: https://github.com/zulip/zulip/blob/master/zerver/management/commands/email_mirror.py

## Credentials needed

#### SSL certificate

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

This section details some basic guidelines for running a Zulip server
for larger organizations (especially >1000 users or 500+ daily active
users).  Zulip's resource needs depend mainly on 3 parameters:
* daily active users (e.g. number of employees if everyone's an
employee)
* total user accounts (can be much larger)
* message volume.

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
  active users, we recommend using a [remote Postgres
  database](postgres.md), but it's not required.

* **RAM:**  We recommended more RAM for larger installations:
    * With 25+ daily active users, 4GB of RAM.
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
  the S3 backend configuration, we recommend 50GB of disk for the OS,
  Zulip software, logs and scratch/free space.  Disk needs when
  storing uploads locally

* **Disk for database:** SSD disk is highly recommended.  For
  installations where most messages have <100 recipients, 10GB per 1M
  messages of history is sufficient plus 1GB per 1000 users is
  sufficient.  If most messages are to public streams with 10K+ users
  subscribed (like on chat.zulip.org), add 20GB per (1000 user
  accounts) per (1M messages to public streams).

* **Example:** When the
  [chat.zulip.org](../contributing/chat-zulip-org.md) community server
  had 12K user accounts (~300 daily actives) and 800K messages of
  history (400K to public streams), it was a default configuration
  single-server installation with 16GB of RAM, 4 cores (essentially
  always idle), and its database was using about 100GB of disk.

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
    [Contact us][contact-support] for help implementing the sharding policy.

Scalability is an area of active development, so if you're unsure
whether Zulip is a fit for your organization or need further advice
[contact Zulip support][contact-support].

[s3-uploads]: ../production/upload-backends.html#s3-backend-configuration
[streaming-replication]: ../production/export-and-import.html#postgres-streaming-replication
[contact-support]: https://zulip.com/help/contact-support
