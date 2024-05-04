class zulip::profile::rabbitmq {
  include zulip::profile::base
  $erlang = $facts['os']['family'] ? {
    'Debian' => 'erlang-base',
    'RedHat' => 'erlang',
  }
  $rabbitmq_packages = [
    $erlang,
    'rabbitmq-server',
  ]

  group { 'rabbitmq':
    ensure => present,
    system => true,
  }
  user { 'rabbitmq':
    ensure  => present,
    comment => 'RabbitMQ messaging server',
    gid     => 'rabbitmq',
    home    => '/var/lib/rabbitmq',
    shell   => '/usr/sbin/nologin',
    system  => true,
    require => Group['rabbitmq'],
  }
  file { '/etc/rabbitmq':
    ensure  => directory,
    owner   => 'rabbitmq',
    group   => 'rabbitmq',
    mode    => '0755',
    require => User['rabbitmq'],
    before  => Package['rabbitmq-server'],
  }
  file { '/etc/rabbitmq/rabbitmq.config':
    ensure => file,
    owner  => 'rabbitmq',
    group  => 'rabbitmq',
    mode   => '0644',
    source => 'puppet:///modules/zulip/rabbitmq/rabbitmq.config',
    # This config file must be installed before the package, so that
    # port 25672 is not even briefly open to the Internet world, which
    # would be a security risk, due to insecure defaults in the
    # RabbitMQ package.
    before => Package['rabbitmq-server'],
    notify => Service['rabbitmq-server'],
  }
  exec { 'warn-rabbitmq-nodename-change':
    command   => "${facts['zulip_scripts_path']}/lib/warn-rabbitmq-nodename-change",
    onlyif    => '[ -f /etc/rabbitmq/rabbitmq-env.conf ] && ! grep -xq NODENAME=zulip@localhost /etc/rabbitmq/rabbitmq-env.conf',
    before    => [
      File['/etc/rabbitmq/rabbitmq-env.conf'],
      Service['rabbitmq-server'],
    ],
    logoutput => true,
    loglevel  => warning,
  }
  file { '/etc/rabbitmq/rabbitmq-env.conf':
    ensure => file,
    owner  => 'rabbitmq',
    group  => 'rabbitmq',
    mode   => '0644',
    source => 'puppet:///modules/zulip/rabbitmq/rabbitmq-env.conf',
    before => Package['rabbitmq-server'],
    notify => [
      Service['rabbitmq-server'],
      Exec['configure-rabbitmq'],
    ],
  }
  package { $rabbitmq_packages:
    ensure => installed,
  }
  # epmd doesn't have an init script, so we just check if it is
  # running, and if it isn't, start it.  Even in case of a race, this
  # won't leak epmd processes, because epmd checks if one is already
  # running and exits if so.
  exec { 'epmd':
    command => 'epmd -daemon',
    unless  => 'which pgrep && pgrep -x epmd >/dev/null',
    require => Package[$erlang],
    path    => '/usr/bin/:/bin/',
  }

  service { 'rabbitmq-server':
    ensure  => running,
    require => [
      Exec['epmd'],
      Package['rabbitmq-server'],
    ],
  }

  exec { 'configure-rabbitmq':
    command     => "${facts['zulip_scripts_path']}/setup/configure-rabbitmq",
    refreshonly => true,
    require     => Service['rabbitmq-server'],
  }
}
