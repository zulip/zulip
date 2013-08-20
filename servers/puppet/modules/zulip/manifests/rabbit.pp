class zulip::rabbit {
  $rabbit_packages = [ "rabbitmq-server" ]
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

  # TODO: Should also call exactly once "servers/configure-rabbitmq"
}
