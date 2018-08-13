class zulip_ops::apache {
  $apache_packages = [# Needed to run Apache with WSGI
                      'apache2',
                      'libapache2-mod-wsgi',
                      ]
  package { $apache_packages: ensure => 'installed' }

  apache2mod { [ 'headers', 'proxy', 'proxy_http', 'rewrite', 'auth_digest', 'ssl' ]:
    ensure  => present,
    require => Package['apache2'],
  }

  file { '/etc/apache2/users/':
    ensure  => directory,
    require => Package['apache2'],
    owner   => 'www-data',
    group   => 'www-data',
    mode    => '0600',
  }

  file { '/etc/apache2/users/wiki':
    ensure  => file,
    require => File['/etc/apache2/users/'],
    owner   => 'www-data',
    group   => 'www-data',
    mode    => '0600',
    source  => 'puppet:///modules/zulip_ops/apache/users',
  }

  file { '/etc/apache2/certs/':
    ensure  => directory,
    require => Package['apache2'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
  }

  file { '/etc/apache2/ports.conf':
    ensure  => file,
    require => Package[apache2],
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
    source  => 'puppet:///modules/zulip_ops/apache/ports.conf',
  }

  file { '/etc/apache2/sites-available/':
    ensure  => directory,
    require => Package[apache2],
    owner   => 'root',
    group   => 'root',
    mode    => '0640',
  }
}
