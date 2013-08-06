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
}
