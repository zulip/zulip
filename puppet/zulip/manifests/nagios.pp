# This manifest installs Zulip's Nagios plugins intended to be on
# localhost on a Nagios server.
#
# Depends on zulip::base to have installed `nagios-plugins-basic`.
class zulip::nagios {
  include zulip::common
  file { "${zulip::common::nagios_plugins_dir}/zulip_nagios_server":
    require => Package[$zulip::common::nagios_plugins],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/nagios_plugins/zulip_nagios_server',
  }
}
