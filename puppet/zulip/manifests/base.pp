class zulip::base {
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

  apt::key {"A529EF65":
    source  =>  "http://apt.zulip.com/ops.asc",
  }

  apt::sources_list {"zulip":
    ensure  => present,
    content => 'deb http://apt.zulip.com/ops wheezy main',
  }

  group { 'zulip':
    ensure     => present,
    gid        => '1000',
  }
  user { 'zulip':
    ensure     => present,
    uid        => '1000',
    gid        => '1000',
    require    => Group['zulip'],
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

  file { '/etc/puppet/puppet.conf':
    ensure     => file,
    mode       => 640,
    source     => 'puppet:///modules/zulip/puppet.conf',
  }

  file { '/etc/security/limits.conf':
    ensure     => file,
    mode       => 640,
    owner      => "root",
    group      => "root",
    source     => 'puppet:///modules/zulip/limits.conf',
  }

  file { '/etc/apt/apt.conf.d/02periodic':
    ensure     => file,
    mode       => 644,
    source     => 'puppet:///modules/zulip/apt/apt.conf.d/02periodic',
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
