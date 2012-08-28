class kandra::profile::teleport inherits kandra::profile::base {


  file { '/etc/teleport_server.yaml':
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/kandra/teleport_server.yaml',
    before => Kandra::Teleport::Part['server'],
    notify => Exec['reload teleport_server'],
  }
  file { '/var/lib/teleport-server':
    ensure => directory,
    owner  => 'root',
    group  => 'root',
    mode   => '0700',
    before => Kandra::Teleport::Part['server'],
  }
  kandra::teleport::part { 'server': }

  # https://goteleport.com/docs/reference/deployment/networking/#ports-with-tls-routing
  kandra::firewall_allow { 'teleport_server_ui': port => 443 }
}
