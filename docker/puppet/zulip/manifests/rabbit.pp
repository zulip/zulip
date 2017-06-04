class zulip::rabbit {
  $rabbit_packages = [
    # Needed to run rabbitmq
    "erlang-base",
    "rabbitmq-server",
  ]
  package { $rabbit_packages: ensure => "installed" }

  file { "/etc/cron.d/rabbitmq-numconsumers":
    require => Package[rabbitmq-server],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/cron.d/rabbitmq-numconsumers",
  }
}
