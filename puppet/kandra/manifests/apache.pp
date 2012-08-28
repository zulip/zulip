class kandra::apache {
  package { 'apache2':
    ensure => installed,
  }
  service { 'apache2':
    require => Package['apache2'],
  }

  apache2mod { [ 'headers', 'proxy', 'proxy_http', 'rewrite', 'auth_digest', 'ssl' ]:
    ensure  => present,
    require => Package['apache2'],
    notify  => Service['apache2'],
  }

  file { '/etc/apache2/certs/':
    ensure  => directory,
    require => Package['apache2'],
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
  }

  file { '/etc/apache2/ports.conf':
    ensure  => file,
    require => Package[apache2],
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    source  => 'puppet:///modules/kandra/apache/ports.conf',
    notify  => Service['apache2'],
  }

  file { '/etc/apache2/sites-available/':
    ensure  => directory,
    require => Package[apache2],
    owner   => 'root',
    group   => 'root',
    mode    => '0750',
  }
}
