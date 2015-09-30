class zulip::rabbit {
  $rabbit_packages = [# Needed to run rabbitmq
                      "erlang-base",
                      "rabbitmq-server",
                      ]
  package { $rabbit_packages: ensure => "installed" }

  file { "/etc/cron.d/rabbitmq-queuesize":
    require => Package[rabbitmq-server],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/rabbitmq-queuesize",
  }
  file { "/etc/cron.d/rabbitmq-numconsumers":
    require => Package[rabbitmq-server],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/rabbitmq-numconsumers",
  }

  file { "/etc/default/rabbitmq-server":
    require => Package[rabbitmq-server],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/rabbitmq/rabbitmq-server",
  }

  file { "/etc/rabbitmq/rabbitmq.config":
    require => Package[rabbitmq-server],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/rabbitmq/rabbitmq.config",
  }

  # epmd doesn't have an init script.  This won't leak epmd processes
  # because epmd checks if one is already running and exits if so.
  #
  # TODO: Ideally we'd still check if it's already running to keep the
  # puppet log for what is being changed clean
  exec { "epmd":
    command => "epmd -daemon",
    require => Package[erlang-base],
    path    => "/usr/bin/:/bin/",
  }

  service { "rabbitmq-server":
    ensure => running,
    require => Exec["epmd"],
  }

  # TODO: Should also call exactly once "configure-rabbitmq"
}
