class zulip::outproxy {
  include zulip::supervisor

  file { '/etc/supervisor/conf.d/outproxy.conf':
    ensure  => file,
    require => Package[supervisor],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/supervisor/conf.d/outproxy.conf',
    notify  => Service['supervisor'],
  }
}
