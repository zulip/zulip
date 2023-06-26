class zulip_ops::profile::zmirror_personals {
  include zulip_ops::profile::base
  include zulip::supervisor

  $zmirror_packages = [# Packages needed to run the mirror
    'libzephyr4-krb5',
    'zephyr-clients',
    'krb5-config',
    'krb5-user',
    # Packages needed to for ctypes access to Zephyr
    'python3-dev',
    'python3-typing-extensions',
  ]
  package { $zmirror_packages:
    ensure  => installed,
  }

  file { '/etc/krb5.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/krb5.conf',
  }

  concat::fragment { '01-supervisor-zmirror':
    order   => '10',
    target  => $zulip::common::supervisor_conf_file,
    content => " ${zulip::common::supervisor_system_conf_dir}/zmirror/*.conf",
  }

  file { ['/home/zulip/api-keys', '/home/zulip/zephyr_sessions', '/home/zulip/ccache',
          '/home/zulip/mirror_status', "${zulip::common::supervisor_system_conf_dir}/zmirror"]:
    ensure => directory,
    mode   => '0755',
    owner  => 'zulip',
    group  => 'zulip',
  }

  file { '/etc/cron.d/test_zephyr_personal_mirrors':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/cron.d/test_zephyr_personal_mirrors',
  }

  file { '/usr/lib/nagios/plugins/zulip_zephyr_mirror':
    require => Package[$zulip::common::nagios_plugins],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip_ops/nagios_plugins/zulip_zephyr_mirror',
  }

  # Allow the relevant UDP ports
  concat::fragment { 'iptables-zmirror.v4':
    target => '/etc/iptables/rules.v4',
    source => 'puppet:///modules/zulip_ops/iptables/zmirror.v4',
    order  => '20',
  }
  concat::fragment { 'iptables-zmirror.v6':
    target => '/etc/iptables/rules.v6',
    source => 'puppet:///modules/zulip_ops/iptables/zmirror.v6',
    order  => '20',
  }
}
