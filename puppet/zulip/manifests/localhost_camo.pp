class zulip::localhost_camo {
  class { 'zulip::camo':
    listen_address => '127.0.0.1',
  }

  # Install nginx configuration to run camo locally
  file { '/etc/nginx/zulip-include/app.d/camo.conf':
    ensure  => file,
    require => Package['nginx-full'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    source  => 'puppet:///modules/zulip/nginx/zulip-include-app.d/camo.conf',
  }
}
