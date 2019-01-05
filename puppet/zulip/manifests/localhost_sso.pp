class zulip::localhost_sso {
  $nginx = $::osfamily ? {
    'debian' => 'nginx-full',
    'redhat' => 'nginx',
  }

  file { '/etc/nginx/zulip-include/app.d/external-sso.conf':
    ensure  => file,
    require => Package[$nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    source  => 'puppet:///modules/zulip/nginx/zulip-include-app.d/external-sso.conf',
  }
}
