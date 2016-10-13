# This class includes all the modules you need to run an entire Zulip
# installation on a single server.  If desired, you can split up the
# different components of a Zulip installation on different servers by
# using the modules below on different machines (the module list is
# stored in `puppet_classes` in /etc/zulip/zulip.conf).  In general,
# every machine should have `zulip::base` and `zulip::apt_repository`
# included, but the various service modules can be arranged on
# different machines or the same machine as desired (corresponding
# configuration in /etc/zulip/settings.py for how to find the various
# services is also required to make this work).
class zulip::voyager {
  include zulip::base
  # zulip::apt_repository must come after zulip::base
  include zulip::apt_repository
  include zulip::app_frontend
  include zulip::postgres_appdb_tuned
  include zulip::memcached
  include zulip::rabbit
  include zulip::redis
  include zulip::localhost_camo
}
