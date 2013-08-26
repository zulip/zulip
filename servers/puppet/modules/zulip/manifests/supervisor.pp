class zulip::supervisor {
  $supervisor_packages = [ "supervisor",]
  package { $supervisor_packages: ensure => "installed" }

  service { "supervisor":
    ensure => running,
    require => [File["/var/log/humbug"],
                Package["supervisor"],
                ],

    hasstatus => true,
    status => "supervisorctl status",

    # The "restart" option in the init script does not work.  We could
    # tell Puppet to fall back to stop/start, which does work, but the
    # better option is to tell supervisord to restart via supervisorctl
    #
    # Idealy we would use the "reread" command, but that does't seem
    # to actually work.
    hasrestart => true,
    restart => "supervisorctl reload"
  }

  file { "/etc/supervisor/supervisord.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/supervisord/supervisord.conf",
    notify => Service["supervisor"],
  }

  exec { "fix_supervisor_socket_permissions":
    command => "chown humbug:humbug /var/run/supervisor.sock",
    unless => "bash -c 'ls -ld /var/run/supervisor.sock | cut -f 3-4 -d\" \"  | grep -q \"^humbug humbug$\"'",
    require => Service["supervisor"],
  }
}
