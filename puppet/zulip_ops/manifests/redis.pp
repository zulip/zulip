class zulip_ops::redis {
  include zulip_ops::base
  include zulip::redis

  # Need redis_password in its own file for Nagios
  file { '/var/lib/nagios/redis_password':
    ensure  => file,
    mode    => '0600',
    owner   => 'nagios',
    group   => 'nagios',
    content => "${zulip::redis::redis_password}\n",
  }
}
