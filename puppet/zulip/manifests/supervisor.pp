class zulip::supervisor {
  $supervisor_service = $zulip::common::supervisor_service

  package { 'supervisor': ensure => 'installed' }

  $system_conf_dir = $zulip::common::supervisor_system_conf_dir
  file { $system_conf_dir:
    ensure  => 'directory',
    require => Package['supervisor'],
    owner   => 'root',
    group   => 'root',
  }

  $conf_dir = $zulip::common::supervisor_conf_dir
  file { $conf_dir:
    ensure  => 'directory',
    require => Package['supervisor'],
    owner   => 'root',
    group   => 'root',
    purge   => true,
    recurse => true,
    notify  => Service[$supervisor_service],
  }

  # These files were moved from /etc/supervisor/conf.d/ into a zulip/
  # subdirectory in 2020-10 in version 4.0; these lines can be removed
  # in Zulip version 5.0 and later.
  file { [
    "${zulip::common::supervisor_system_conf_dir}/cron.conf",
    "${zulip::common::supervisor_system_conf_dir}/nginx.conf",
    "${zulip::common::supervisor_system_conf_dir}/thumbor.conf",
    "${zulip::common::supervisor_system_conf_dir}/zulip_db.conf",
    "${zulip::common::supervisor_system_conf_dir}/zulip.conf",
  ]:
    ensure => absent,
  }

  # In the dockervoyager environment, we don't want/need supervisor to be started/stopped
  # /bin/true is used as a decoy command, to maintain compatibility with other
  # code using the supervisor service.
  #
  # This logic is definitely a hack, but it's less bad than the old hack :(
  $puppet_classes = zulipconf('machine', 'puppet_classes', undef)
  if $puppet_classes == 'zulip::dockervoyager' {
    service { $supervisor_service:
      ensure     => running,
      require    => [
        File['/var/log/zulip'],
        Package['supervisor'],
      ],
      hasstatus  => true,
      status     => '/bin/true',
      hasrestart => true,
      restart    => '/bin/true',
    }
    exec { 'supervisor-restart':
      refreshonly => true,
      command     => '/bin/true',
    }
  } else {
    service { $supervisor_service:
      ensure     => running,
      require    => [
        File['/var/log/zulip'],
        Package['supervisor'],
      ],
      hasstatus  => true,
      status     => 'supervisorctl status',
      # Restarting the whole supervisorctl on every update to its
      # configuration files has the unfortunate side-effect of
      # restarting all of the services it controls; this results in an
      # unduly large disruption.  The better option is to tell
      # supervisord to reread its config via supervisorctl and then to
      # "update".  You need to do both -- after a "reread", supervisor
      # won't actually take action based on the changed configuration
      # until you do an "update" (I assume this is so you can check if
      # your config file parses without doing anything, but it's
      # really confusing).
      #
      # If restarting supervisor itself is necessary, see
      # Exec['supervisor-restart']
      #
      # Also, to handle the case that supervisord wasn't running at
      # all, we check if it is not running and if so, start it.
      #
      # We use supervisor[d] as the pattern so the bash/grep commands
      # don't match.
      hasrestart => true,
      # lint:ignore:140chars
      restart    => "bash -c 'if pgrep -f supervisor[d] >/dev/null; then supervisorctl reread && supervisorctl update; else ${zulip::common::supervisor_start}; fi'",
      # lint:endignore
    }
    exec { 'supervisor-restart':
      refreshonly => true,
      command     => $zulip::common::supervisor_reload,
    }
  }

  file { $zulip::common::supervisor_conf_file:
    ensure  => file,
    require => Package[supervisor],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/supervisor/supervisord.conf.erb'),
    notify  => Exec['supervisor-restart'],
  }
}
