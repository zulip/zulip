class zulip::rabbit {
  $erlang = $::osfamily ? {
    'debian' => 'erlang-base',
    'redhat' => 'erlang',
  }
  $rabbit_packages = [# Needed to run rabbitmq
                      $erlang,
                      'rabbitmq-server',
                      ]
  package { $rabbit_packages: ensure => 'installed' }

  file { '/etc/cron.d/rabbitmq-queuesize':
    ensure  => file,
    require => Package[rabbitmq-server],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/cron.d/rabbitmq-queuesize',
  }
  file { '/etc/cron.d/rabbitmq-numconsumers':
    ensure  => file,
    require => Package[rabbitmq-server],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/cron.d/rabbitmq-numconsumers',
  }

  file { '/etc/default/rabbitmq-server':
    ensure  => file,
    require => Package[rabbitmq-server],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/rabbitmq/rabbitmq-server',
  }

  file { '/etc/rabbitmq/rabbitmq.config':
    ensure  => file,
    require => Package[rabbitmq-server],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/rabbitmq/rabbitmq.config',
  }

  $rabbitmq_nodename = zulipconf('rabbitmq', 'nodename', '')
  if $rabbitmq_nodename != '' {
    file { '/etc/rabbitmq':
      ensure => 'directory',
      owner  => 'root',
      group  => 'root',
      mode   => '0755',
    }

    file { '/etc/rabbitmq/rabbitmq-env.conf':
      ensure  => file,
      require => File['/etc/rabbitmq'],
      before  => [Package[rabbitmq-server], Service[rabbitmq-server]],
      owner   => 'root',
      group   => 'root',
      mode    => '0644',
      content => template('zulip/rabbitmq-env.conf.template.erb'),
    }
  }
  # epmd doesn't have an init script, so we just check if it is
  # running, and if it isn't, start it.  Even in case of a race, this
  # won't leak epmd processes, because epmd checks if one is already
  # running and exits if so.
  exec { 'epmd':
    command => 'epmd -daemon',
    unless  => 'pgrep -f epmd >/dev/null',
    require => Package[$erlang],
    path    => '/usr/bin/:/bin/',
  }

  service { 'rabbitmq-server':
    ensure  => running,
    require => [Exec['epmd'],
                File['/etc/rabbitmq/rabbitmq.config'],
                File['/etc/default/rabbitmq-server']],
  }

  # TODO: Should also call exactly once "configure-rabbitmq"
}
