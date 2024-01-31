class zulip_ops::profile::redis inherits zulip_ops::profile::base {
  include zulip::profile::redis
  include zulip_ops::prometheus::redis

  # Need redis_password in its own file for Nagios
  file { '/var/lib/nagios/redis_password':
    ensure  => file,
    mode    => '0600',
    owner   => 'nagios',
    group   => 'nagios',
    content => "${zulip::profile::redis::redis_password}\n",
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
  zulip_ops::user_dotfiles { 'redistunnel':
    authorized_keys => true,
  }
}
