class zulip_ops::zmirror {
  include zulip_ops::base
  include zulip_ops::apt_repository_debathena
  include zulip::supervisor

  $zmirror_packages = [# Packages needed to run the mirror
    'libzephyr4-krb5',
    'zephyr-clients',
    'krb5-config',
    'krb5-user',
    'debathena-kerberos-config',
    'debathena-zephyr-config',
    # Packages needed to build pyzephyr
    'libzephyr-dev',
    'comerr-dev',
    'python3-dev',
    'python-dev',
    'cython3',
    'cython',
  ]
  package { $zmirror_packages:
    ensure  => 'installed',
    require => Exec['setup_apt_repo_debathena'],
  }

  apt::source {'debathena':
    location    => 'http://debathena.mit.edu/apt',
    release     => 'xenial',
    repos       => 'debathena debathena-config',
    key         => 'D1CD49BDD30B677273A75C66E4EE62700D8A9E8F',
    key_source  => 'https://debathena.mit.edu/apt/debathena-archive.asc',
    include_src => true,
  }

  file { '/etc/supervisor/conf.d/zmirror.conf':
    ensure  => file,
    require => Package[supervisor],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/supervisor/conf.d/zmirror.conf',
    notify  => Service['supervisor'],
  }

  file { '/etc/cron.d/zephyr-mirror':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/cron.d/zephyr-mirror',
  }

  file { '/etc/default/zephyr-clients.debathena':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/zephyr-clients.debathena',
  }

  file { '/usr/lib/nagios/plugins/zulip_zephyr_mirror':
    require => Package[nagios-plugins-basic],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip_ops/nagios_plugins/zulip_zephyr_mirror',
  }

  # TODO: Do the rest of our setup, which includes at least:
  # Building python-zephyr after cloning it from https://github.com/ebroder/python-zephyr
  # Putting tabbott/extra's keytab on the system at /home/zulip/tabbott.extra.keytab
}
