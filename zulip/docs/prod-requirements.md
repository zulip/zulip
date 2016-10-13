# Requirements

Note that if you just want to play around with Zulip and see what it looks
like, it is easier to install it in a development environment
following [these
instructions](readme-symlink.html#installing-the-zulip-development-environment),
since then you don't need to worry about setting up SSL certificates and an
authentication mechanism. Or, you can check out the
[developers' chatroom](http://zulip.tabbott.net/) (a public, running Zulip
instance).

## Server

#### Hardware Specifications

* CPU and Memory: For installations with 100+ users you'll need a minimum of
  **2 CPUs** and **4GB RAM**. For installations with fewer users, 1 CPU and 2GB
  RAM might be sufficient. We strong recommend against installing with less
  than 2GB of RAM, as you will likely experience out of memory issues.

* Disk space: You'll need at least 10GB of free disk space. If you intend to
  store uploaded files locally rather than on S3 you will likely need more.

#### Network and Security Specifications

* Outgoing HTTP(S) access to the public Internet. If you want to be able to
  send email from Zulip, you'll also need SMTP access.

#### Operating System

Ubuntu 14.04 Trusty and Ubuntu 16.04 Xenial are supported for running
Zulip in production. 64-bit is recommended.

#### Domain name

You should already have a domain name available for your Zulip
production instance. In order to generate valid SSL certificates with Let's
Encrypt, and to enable other services such as Google Authentication, you'll
need to update the domains A record to point to your production server.

## Credentials needed

#### SSL Certificate

* SSL Certificate for the host you're putting this on (e.g. zulip.example.com).
  The installation instructions contain documentation for how to get an SSL
  certificate for free using [LetsEncrypt](https://letsencrypt.org/).

#### Outgoing email

* Email credentials Zulip can use to send outgoing emails to users
  (e.g. email address confirmation emails during the signup process,
  missed message notifications, password reminders if you're not using
  SSO, etc.).

Once you have met these requirements, see [full instructions for installing
Zulip in production](prod-install.html).
