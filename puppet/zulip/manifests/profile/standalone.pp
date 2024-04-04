# @summary Complete Zulip server on one server
#
# This class includes all the modules you need to run an entire Zulip
# installation on a single server.  If desired, you can split up the
# different `zulip::profile::*` components of a Zulip installation
# onto different servers:
#
#  - zulip::profile::app_frontend
#  - zulip::profile::memcached
#  - zulip::profile::postgresql
#  - zulip::profile::rabbitmq
#  - zulip::profile::redis
#  - zulip::profile::smokescreen
#
# See the corresponding configuration in /etc/zulip/settings.py for
# how to find the various services is also required to make this work.

class zulip::profile::standalone {
  include zulip::profile::standalone_nodb
  include zulip::profile::postgresql
}
