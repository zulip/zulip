# @summary Complete Zulip server, except the database server.
#
# This includes all of the parts necessary to run an entire Zulip
# installation on a single server, except the database.  It is assumed
# that the PostgreSQL database is either hosted on another server with
# the `zulip::profile::postgresql` class applied, or a cloud-managed
# database is used (e.g. AWS RDS).
#
# @see https://zulip.readthedocs.io/en/latest/production/deployment.html#using-zulip-with-amazon-rds-as-the-database
class zulip::profile::standalone_nodb {
  include zulip::profile::app_frontend
  include zulip::profile::memcached
  include zulip::profile::rabbitmq
  include zulip::profile::redis
  include zulip::localhost_camo
}
