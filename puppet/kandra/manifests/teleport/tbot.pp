# @summary Provide a local application proxy
# https://goteleport.com/docs/reference/machine-workload-identity/configuration/#application-proxy
class kandra::teleport::tbot {
  include kandra::teleport::base

  file { '/etc/tbot.yaml':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/kandra/tbot.yaml',
    before => Service['tbot'],
    notify => Exec['reload tbot'],
  }

  file { '/etc/systemd/system/tbot.service':
    require => [
      Package[teleport],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/kandra/tbot.service',
    notify  => [Exec['reload systemd'], Service['tbot']],
  }

  file { ['/var/lib/teleport/bot', '/var/lib/teleport/bot-identity']:
    ensure  => directory,
    owner   => 'teleport',
    group   => 'teleport',
    mode    => '0644',
    require => Service['teleport'],
    before  => Service['tbot'],
  }

  service {'tbot':
    ensure  => running,
    enable  => true,
    require => [Service['teleport'], Exec['reload systemd']],
  }

  # See the equivalent in kandra::teleport::part.
  exec { 'reload tbot':
    command     => '/bin/systemctl reload tbot',
    refreshonly => true,
    require     => Service['tbot'],
  }
}
