# Requirements

Note that if you just want to play around with Zulip and see what it
looks like, it is easier to install it in a development environment
following
[these instructions](readme-symlink.html#installing-the-zulip-development-environment),
since then you don't need to worry about setting up SSL certificates
and an authentication mechanism.  Or, you can check out the
[Zulip development community server](chat-zulip-org.html).

## Server

#### General

The installer expects Zulip to be the **only thing** running on the
system; it will install system packages with `apt` (like nginx,
postgresql, and redis) and configure them for its own use.  We
strongly recommend using either a fresh machine instance in a cloud
provider, a fresh VM, or a dedicated machine.  If you decide to
disregard our advice and use a server that hosts other services, we
can't support you, but
[we do have some notes on issues you'll encounter](prod-install-existing-server.html).

#### Operating System

Ubuntu 14.04 Trusty and Ubuntu 16.04 Xenial are supported for running
Zulip in production. 64-bit is recommended.

#### Hardware Specifications

* CPU and Memory: For installations with 100+ users you'll need a
  minimum of **2 CPUs** and **4GB RAM**. For installations with fewer
  users, 1 CPU and 2GB RAM is sufficient. We strongly recommend against
  installing with less than 2GB of RAM, as you will likely experience
  out of memory issues installing dependencies.  We recommend against
  using highly CPU-limited servers like the AWS `t2` style instances
  for organizations with a hundreds of users (active or no).

  See our
  [documentation on scalability](prod-maintain-secure-upgrade.html#scalability)
  for advice on hardware requirements for larger organizations.

* Disk space: You'll need at least 10GB of free disk space for a
  server with dozens of users. If you intend to store uploaded files
  locally rather than on S3 you will likely need more, depending how
  often your users upload large files.  You'll eventually need 100GB
  or more if you have thousands of active users or millions of total
  messages sent.

#### Network and Security Specifications

* Incoming HTTPS access (usually port 443, though this is
  configurable) from the networks where your users are (usually, the
  public Internet).  If you also open port 80, Zulip will redirect
  users to HTTPS rather than not working when users type
  e.g. `http://zulip.example.com` in their browser.  If you are using
  Zulip's [incoming email integration][email-mirror-code] you may also
  need incoming port 25 open.

[email-mirror-code]: https://github.com/zulip/zulip/blob/master/zerver/management/commands/email_mirror.py

* Outgoing HTTP(S) access (ports 80 and 443) to the public Internet so
  that Zulip can properly manage inline image previews.  You'll also
  need outgoing SMTP access to your SMTP server (the standard port for
  this is 587) so that Zulip can send email.

#### Domain name

You should already have a domain name available for your Zulip
production instance. In order to generate valid SSL certificates with Let's
Encrypt, and to enable other services such as Google Authentication, you'll
need to update the domain's A record to point to your production server.

## Credentials needed

#### SSL Certificate

* An SSL certificate for the host you're putting this on (e.g.,
  zulip.example.com).  If you don't have an SSL solution already, read
  about [getting an SSL certificate for free](ssl-certificates.html) using
  Let's Encrypt.

#### Outgoing email

* Outgoing email (SMTP) credentials that Zulip can use to send
  outgoing emails to users (e.g. email address confirmation emails
  during the signup process, missed message notifications, password
  reset, etc.).  If you don't have an existing outgoing SMTP solution,
  read about
  [free outgoing SMTP options and options for prototyping](prod-email.html#free-outgoing-email-services).

Once you have met these requirements, see [full instructions for installing
Zulip in production](prod-install.html).
