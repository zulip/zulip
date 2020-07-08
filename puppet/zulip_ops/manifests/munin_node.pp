class zulip_ops::munin_node {
  zulip::safepackage { ['munin-node', 'munin-plugins-extra']: ensure => 'installed' }

  service { 'munin-node':
    ensure  => running,
    require => Package['munin-node'],
  }

  file { '/etc/munin/munin-node.conf':
    require => Package['munin-node'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/munin/munin-node.conf',
    notify  => Service['munin-node'],
  }

  file { '/etc/munin/plugin-conf.d':
    require => Package['munin-node'],
    recurse => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/munin/plugin-conf.d',
    notify  => Service['munin-node'],
  }

  file { ['/usr/local/munin', '/usr/local/munin/lib', '/usr/local/munin/lib/plugins']:
    ensure => directory,
  }
}
