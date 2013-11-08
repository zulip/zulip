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
    status => "supervisorctl status",

    # The "restart" option in the init script does not work.  We could
    # tell Puppet to fall back to stop/start, which does work, but the
    # better option is to tell supervisord to reread its config via
    # supervisorctl and then to "update".  You need to do both --
    # after a "reread", supervisor won't actually take actual based on
    # the changed configuration until you do an "update" (I assume
    # this is so you can check if your config file parses without
    # doing anything, but it's really confusing)
    hasrestart => true,
    restart => "bash -c 'supervisorctl reread && supervisorctl update'"
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
