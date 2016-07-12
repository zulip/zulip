# Requirements for Zulip in production

* Server running Ubuntu Trusty
* At least 2 CPUs for production use with 100+ users
* At least 4GB of RAM for production use with 100+ users.  We **strongly
  recommend against installing with less than 2GB of RAM**, as you will
  likely experience OOM issues.  In the future we expect Zulip's RAM
  requirements to decrease to support smaller installations (see
  https://github.com/zulip/zulip/issues/32).
* At least 10GB of free disk for production use (more may be required
  if you intend to store uploaded files locally rather than in S3
  and your team uses that feature extensively)
* Outgoing HTTP(S) access to the public Internet.
* SSL Certificate for the host you're putting this on
  (e.g. zulip.example.com).
* Email credentials Zulip can use to send outgoing emails to users
  (e.g. email address confirmation emails during the signup process,
  missed message notifications, password reminders if you're not using
  SSO, etc.).

Note that if you just want to play around with Zulip and see what it
looks like, it is easier to install it in a development environment
following [these
instructions](readme-symlink.html#installing-the-zulip-development-environment),
since then you don't need to worry about setting up SSL certificates
and an authentication mechanism.  Or, you can check out the
[developers' chatroom (a public, running Zulip
instance)](http://zulip.tabbott.net/).

For more details, see [full instructions for installing Zulip in
production](prod-install.html).
