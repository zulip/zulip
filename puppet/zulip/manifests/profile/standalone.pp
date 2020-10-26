# This class includes all the modules you need to run an entire Zulip
# installation on a single server.  If desired, you can split up the
# different `zulip::profile::*` components of a Zulip installation on
# different servers by using the modules below on different machines
# (the module list is stored in `puppet_classes` in
# /etc/zulip/zulip.conf).  See the corresponding configuration in
# /etc/zulip/settings.py for how to find the various services is also
# required to make this work.
class zulip::profile::standalone {
  include zulip::profile::base
  include zulip::profile::app_frontend
  include zulip::profile::postgresql
  include zulip::profile::redis
  include zulip::profile::memcached
  include zulip::profile::rabbitmq
  if $::osfamily == debian {
    # camo is only required on Debian-based systems as part of
    # our migration towards not including camo at all.
    include zulip::localhost_camo
  }
  include zulip::static_asset_compiler
}
