# @summary Adds a systemd service named teleport_$name
#
define kandra::teleport::part() {
  $part = $name

  include zulip::systemd_daemon_reload
  file { "/etc/systemd/system/teleport_${part}.service":
    require => [
      Package[teleport],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('kandra/teleport.service.template.erb'),
    notify  => [Exec['reload systemd'], Service["teleport_${part}"]],
  }

  service {"teleport_${part}":
    ensure  => running,
    enable  => true,
    require => [Service['supervisor'], Service['teleport'], Exec['reload systemd']],
  }

  # Notify this from YAML config changes (rather than the service)
  # to get a SIGHUP-based graceful restart -- Teleport forks a new
  # daemon and drains the old -- instead of a hard stop+start.
  exec { "reload teleport_${part}":
    command     => "/bin/systemctl reload teleport_${part}",
    refreshonly => true,
    require     => Service["teleport_${part}"],
  }
}
