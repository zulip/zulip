class zulip::base {
  include apt
  $base_packages = [ # Basic requirements for effective operation of a server
                     "ntp",
                     # This is just good practice
                     "molly-guard",
                     # Dependencies of our API
                     "python-requests",
                     "python-simplejson",
                     # For development/debugging convenience
                     "ipython",
                     "screen",
                     "strace",
                     "vim",
                     "moreutils",
                     "emacs23-nox",
                     "git",
                     "puppet-el",
                     "host",
                     ]
  package { $base_packages: ensure => "installed" }

  group { 'zulip':
    ensure     => present,
  }

  user { 'zulip':
    ensure     => present,
    require    => Group['zulip'],
    gid        => 'zulip',
    shell      => '/bin/bash',
    home       => '/home/zulip',
    managehome => true,
  }

  file { '/etc/zulip':
    ensure     => 'directory',
    mode       => 644,
    owner      => 'zulip',
    group      => 'zulip',
  }

  file { '/etc/security/limits.conf':
    ensure     => file,
    mode       => 640,
    owner      => "root",
    group      => "root",
    source     => 'puppet:///modules/zulip/limits.conf',
  }

  # This directory is written to by cron jobs for reading by Nagios
  file { '/var/lib/nagios_state/':
    ensure     => directory,
    group      => 'zulip',
    mode       => 774,
  }

  file { '/var/log/zulip':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
    mode   => 640,
  }

  file { '/var/log/zulip/queue_error':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
    mode   => 640,
  }
}
