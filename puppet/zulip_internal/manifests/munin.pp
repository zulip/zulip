class zulip_internal::munin {
  include zulip::supervisor

  $munin_packages = [# Packages needed for munin
                     "munin",
                     "autossh",
                     ]
  package { $munin_packages: ensure => "installed" }

  # If you add a new Munin node, change the number of autossh processes that we
  # check for with Nagios.

  $hosts = ["trac",
            "zmirror",
            "staging",
            "git",
            "bots",
            "prod0",
            "stats",
            "postgres1",
            "postgres3",
            "redis0",
            ]

  file { "/etc/munin":
    require => Package["munin"],
    recurse => true,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip_internal/munin"
  }

  file { "/etc/munin/munin.conf":
    require => [ Package["munin"], File["/etc/munin"] ],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    content => template("zulip_internal/munin/munin.conf.erb")
  }

  file { "/etc/supervisor/conf.d/munin_tunnels.conf":
    require => Package["supervisor", "autossh"],
    ensure => file,
    mode   => 644,
    owner  => "root",
    group  => "root",
    content => template("zulip_internal/supervisor/conf.d/munin_tunnels.conf.erb"),
    notify => Service["supervisor"]
  }
}
