class zulip::certbot {
  package { 'certbot':
    ensure => installed,
  }
  file { ['/etc/letsencrypt/renewal-hooks', '/etc/letsencrypt/renewal-hooks/deploy']:
    ensure  => directory,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    require => Package[certbot],
  }
}
