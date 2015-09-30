class zulip::supervisor {
  $supervisor_packages = [# Needed to run supervisor
                          "supervisor",
                          ]
  package { $supervisor_packages: ensure => "installed" }

  service { "supervisor":
    ensure => running,
    require => [File["/var/log/zulip"],
                Package["supervisor"],
                ],

    hasstatus => true,
    status => "supervisorctl status"
  }

  file { "/etc/supervisor/supervisord.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/supervisor/supervisord.conf",
    notify => Service["supervisor"],
  }
}
