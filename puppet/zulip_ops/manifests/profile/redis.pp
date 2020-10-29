class zulip_ops::profile::redis inherits zulip_ops::profile::base {
  include zulip::profile::redis

  # Need redis_password in its own file for Nagios
  file { '/var/lib/nagios/redis_password':
    ensure  => file,
    mode    => '0600',
    owner   => 'nagios',
    group   => 'nagios',
    content => "${zulip::profile::redis::redis_password}\n",
  }
}
