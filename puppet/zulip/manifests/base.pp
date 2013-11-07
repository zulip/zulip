class zulip::base {
  $base_packages = [ "screen", "strace", "vim", "emacs23-nox", "git", "python-tz",
                     "sqlite3", "ntp", "python-simplejson", "host",
                     "openssh-server", "python-pip", "puppet-el", "mosh",
                     "iptables-persistent", "postgresql-client-9.1", "molly-guard",
		     "debian-goodies", "moreutils", "python-requests", "ipython",
                     "python-boto", "python-netifaces" ]
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

  file { '/etc/iptables/rules':
    ensure     => file,
    mode       => 600,
    source     => 'puppet:///modules/zulip/iptables/rules',
    require    => Package['iptables-persistent'],
  }
  service { 'iptables-persistent':
    ensure     => running,

    # Because there is no running process for this service, the normal status
    # checks fail.  Because puppet then thinks the service has been manually
    # stopped, it won't restart it.  This fake status command will trick puppet
    # into thinking the service is *always* running (which in a way it is, as
    # iptables is part of the kernel.)
    hasstatus => true,
    status => "/bin/true",

    # Under Debian, the "restart" parameter does not reload the rules, so tell
    # Puppet to fall back to stop/start, which does work.
    hasrestart => false,

    subscribe  => File['/etc/iptables/rules'],
  }
}
