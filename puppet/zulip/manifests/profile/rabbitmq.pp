class zulip::profile::rabbitmq {
  include zulip::profile::base
  $erlang = $::osfamily ? {
    'debian' => 'erlang-base',
    'redhat' => 'erlang',
  }
  $rabbitmq_packages = [
    $erlang,
    'rabbitmq-server',
  ]
  package { $rabbitmq_packages: ensure => 'installed' }

  # Removed 2020-09 in version 4.0; these lines can be removed in
  # Zulip version 5.0 and later.
  file { ['/etc/cron.d/rabbitmq-queuesize', '/etc/cron.d/rabbitmq-numconsumers']:
    ensure => absent,
  }

  file { '/etc/rabbitmq':
    ensure => 'directory',
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
  }
  file { '/etc/rabbitmq/rabbitmq.config':
    ensure  => file,
    require => Package[rabbitmq-server],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/rabbitmq/rabbitmq.config',
  }
  exec { 'warn-rabbitmq-nodename-change':
    command   => "${::zulip_scripts_path}/lib/warn-rabbitmq-nodename-change",
    onlyif    => '[ -f /etc/rabbitmq/rabbitmq-env.conf ] && ! grep -xq NODENAME=zulip@localhost /etc/rabbitmq/rabbitmq-env.conf',
    before    => [
      File['/etc/rabbitmq/rabbitmq-env.conf'],
      Service['rabbitmq-server'],
    ],
    logoutput => true,
    loglevel  => 'warning',
  }
  file { '/etc/rabbitmq/rabbitmq-env.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/rabbitmq/rabbitmq-env.conf',
    before => Package['rabbitmq-server'],
    notify => [
      Service['rabbitmq-server'],
      Exec['configure-rabbitmq'],
    ],
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
    require => [Exec['epmd'],
                File['/etc/rabbitmq/rabbitmq.config'],
                File['/etc/default/rabbitmq-server']],
  }

  exec { 'configure-rabbitmq':
    command     => "${::zulip_scripts_path}/setup/configure-rabbitmq",
    refreshonly => true,
    require     => Service['rabbitmq-server'],
  }
}
