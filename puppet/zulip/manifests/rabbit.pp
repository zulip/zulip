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

  $rabbitmq_nodename = zulipconf("rabbitmq", "nodename", "")
  if $rabbitmq_nodename != "" {
    file { "/etc/rabbitmq/rabbitmq-env.conf":
      require => Package[rabbitmq-server],
      before => Service[rabbitmq-server],
      ensure => file,
      owner  => "root",
      group  => "root",
      mode => 644,
      content => template("zulip/rabbitmq-env.conf.template.erb"),
    }
  }
  # epmd doesn't have an init script, so we just check if it is
  # running, and if it isn't, start it.  Even in case of a race, this
  # won't leak epmd processes, because epmd checks if one is already
  # running and exits if so.
  exec { "epmd":
    command => "epmd -daemon",
    unless => "pgrep -f epmd >/dev/null",
    require => Package[erlang-base],
    path    => "/usr/bin/:/bin/",
  }

  service { "rabbitmq-server":
    ensure => running,
    require => [Exec["epmd"],
                File["/etc/rabbitmq/rabbitmq.config"],
                File["/etc/default/rabbitmq-server"]],
  }

  # TODO: Should also call exactly once "configure-rabbitmq"
}
