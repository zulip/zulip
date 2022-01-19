class zulip_ops::profile::zmirror_personals {
  include zulip_ops::profile::base
  include zulip::supervisor

  $zmirror_packages = [# Packages needed to run the mirror
    'libzephyr4-krb5',
    'zephyr-clients',
    'krb5-config',
    'krb5-user',
    # Packages needed to build pyzephyr
    'libzephyr-dev',
    'comerr-dev',
    'python3-dev',
    'python2.7-dev',
    'cython3',
    'cython',
  ]
  package { $zmirror_packages:
    ensure  => 'installed',
  }

  file { '/etc/krb5.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/krb5.conf',
  }

  file { ['/home/zulip/api-keys', '/home/zulip/zephyr_sessions', '/home/zulip/ccache',
          '/home/zulip/mirror_status']:
    ensure => directory,
    mode   => '0644',
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

  # TODO: Do the rest of our setup, which includes at least:
  # Building patched libzephyr4-krb5 from davidben's roost branch and installing that
  #  (https://github.com/davidben/zephyr/commit/252258d38ebd0e79b261db336c1f74f261b77128)
  #  (to add ZLoadSession/ZDumpSession).
  # Building python-zephyr after cloning it from https://github.com/ebroder/python-zephyr
  #  (Patched with https://github.com/ebroder/python-zephyr/commit/d00cca474ed361439e68246e2687cdc4ea906de3)
}
