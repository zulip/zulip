class zulip::supervisor {
  package { 'supervisor': ensure => 'installed' }

  if $::osfamily == 'redhat' {
    file { $zulip::common::supervisor_conf_dir:
      ensure => 'directory',
      owner  => 'root',
      group  => 'root',
    }
  }

  $supervisor_service = $zulip::common::supervisor_service

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
    source  => 'puppet:///modules/zulip/supervisor/supervisord.conf',
    notify  => Exec['supervisor-restart'],
  }

  # We need a block here to handle deleting the old thumbor.conf file,
  # unless zulip::thumbor has been enabled. It would be cleaner
  # to use tidy instead of exec here, but notify is broken with it
  # (https://tickets.puppetlabs.com/browse/PUP-6021)
  # so we wouldn't be able to notify the supervisor service.
  $thumbor_enabled = defined(Class['zulip::thumbor'])
  if !$thumbor_enabled {
    exec { 'cleanup_thumbor_supervisor_conf_file':
      command => "rm ${zulip::common::supervisor_conf_dir}/thumbor.conf",
      onlyif  => "test -e ${zulip::common::supervisor_conf_dir}/thumbor.conf",
      notify  => Service[$zulip::common::supervisor_service],
    }
  }
}
