class zulip_ops::munin_server {
  include zulip_ops::base
  include zulip::supervisor

  $munin_packages = [
    'munin',
    'autossh',
    'libapache2-mod-fcgid',
  ]
  package { $munin_packages: ensure => 'installed' }

  $default_host_domain = zulipconf('nagios', 'default_host_domain', undef)
  $hosts = zulipconf_nagios_hosts()

  file { '/etc/munin/apache.conf':
    require => Package['munin-node'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip_ops/munin/apache.conf'
    notify  => Service['munin-node'],
  }

  file { '/etc/munin/munin.conf':
    ensure  => file,
    require => Package['munin'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip_ops/munin/munin.conf.erb'),
  }

  file { '/etc/supervisor/conf.d/munin_tunnels.conf':
    ensure  => file,
    require => Package['supervisor', 'autossh'],
    mode    => '0644',
    owner   => 'root',
    group   => 'root',
    content => template('zulip_ops/supervisor/conf.d/munin_tunnels.conf.erb'),
    notify  => Service['supervisor'],
  }
}
