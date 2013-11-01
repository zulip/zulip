class zulip-internal::zmirror {
  include zulip-internal::base
  include zulip::supervisor

  $zmirror_packages = [ "cython", "libzephyr-dev", "comerr-dev", "python-dev", "libzephyr4-krb5", "zephyr-clients",
                        "krb5-config", "krb5-user", "krb5-clients", "debathena-kerberos-config", "debathena-zephyr-config"]
  package { $zmirror_packages: ensure => "installed" }

  file { '/etc/apt/sources.list.d/debathena.list':
    ensure     => file,
    mode       => 644,
    owner      => "root",
    group      => "root",
    source     => 'puppet:///modules/zulip-internal/debathena.list',
  }
  file { "/etc/supervisor/conf.d/zmirror.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip-internal/supervisor/conf.d/zmirror.conf",
    notify => Service["supervisor"],
  }

  file { "/etc/cron.d/zephyr-mirror":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip-internal/cron.d/zephyr-mirror",
  }

  file { "/etc/defaults/zephyr-clients.debathena":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip-internal/zephyr-clients.debathena",
  }

  # TODO: Do the rest of our setup, which includes at least:
  # Building python-zephyr after cloning it from https://github.com/ebroder/python-zephyr
  # Putting tabbott/extra's keytab on the system at /home/zulip/tabbott.extra.keytab
}
