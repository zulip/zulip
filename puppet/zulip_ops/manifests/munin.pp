class zulip_ops::munin {
  include zulip::supervisor

  $munin_packages = [# Packages needed for munin
                     "munin",
                     "autossh",
                     # Packages needed for munin website
                     'libapache2-mod-fcgid',
                     ]
  package { $munin_packages: ensure => "installed" }

  $hosts_domain = zulipconf("nagios", "hosts_domain", undef)
  $hosts = $zulip_ops::base::hosts

  file { "/etc/munin":
    require => Package["munin"],
    recurse => true,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip_ops/munin"
  }

  file { "/etc/munin/munin.conf":
    require => [ Package["munin"], File["/etc/munin"] ],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    content => template("zulip_ops/munin/munin.conf.erb")
  }

  file { "/etc/supervisor/conf.d/munin_tunnels.conf":
    require => Package["supervisor", "autossh"],
    ensure => file,
    mode   => 644,
    owner  => "root",
    group  => "root",
    content => template("zulip_ops/supervisor/conf.d/munin_tunnels.conf.erb"),
    notify => Service["supervisor"]
  }
}
