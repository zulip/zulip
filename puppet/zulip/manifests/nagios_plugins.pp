# @summary Installs a subdirectory from puppet/zulip/files/nagios_plugins/
define zulip::nagios_plugins () {
  include zulip::common

  file { "${zulip::common::nagios_plugins_dir}/${name}":
    require => Package[$zulip::common::nagios_plugins],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => "puppet:///modules/zulip/nagios_plugins/${name}",
  }
}
