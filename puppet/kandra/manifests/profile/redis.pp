class kandra::profile::redis inherits kandra::profile::base {
  include zulip::profile::redis
  include kandra::prometheus::redis

  zulip::sysctl { 'redis-somaxconn':
    key   => 'net.core.somaxconn',
    value => '65535',
  }

  # Need redis_password in its own file for Nagios
  file { '/var/lib/nagios/redis_password':
    ensure  => file,
    mode    => '0600',
    owner   => 'nagios',
    group   => 'nagios',
    content => "${zulip::profile::redis::redis_password}\n",
  }

  group { 'redistunnel':
    ensure => present,
    gid    => '1080',
  }
  user { 'redistunnel':
    ensure     => present,
    uid        => '1080',
    gid        => '1080',
    groups     => ['zulip'],
    shell      => '/bin/true',
    home       => '/home/redistunnel',
    managehome => true,
  }
  kandra::user_dotfiles { 'redistunnel':
    authorized_keys => true,
  }
}
