# @summary Adds a systemd service named teleport_$name
#
define zulip_ops::teleport::part() {
  $part = $name
  file { "/etc/systemd/system/teleport_${part}.service":
    require => [
      Package[teleport],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/teleport.service.template.erb'),
    notify  => Service["teleport_${part}"],
  }

  service {"teleport_${part}":
    ensure  => running,
    enable  => true,
    require => [Service['supervisor'], Service['teleport']],
  }
}
