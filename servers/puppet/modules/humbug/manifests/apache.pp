class humbug::apache {
  $apache_packages = [ "apache2", "libapache2-mod-wsgi", ]
  package { $apache_packages: ensure => "installed" }

  apache2mod { [ "headers", "proxy", "proxy_http", "rewrite", "auth_digest", "ssl" ]:
    ensure => present,
  }

  file { "/etc/apache2/users/":
    ensure   => directory,
    owner    => "www-data",
    group    => "www-data",
    mode     => 600,
  }

  file { "/etc/apache2/users/wiki":
    require => File["/etc/apache2/users/"],
    ensure => file,
    owner  => "www-data",
    group  => "www-data",
    mode => 600,
    source => "puppet:///modules/humbug/apache/users",
  }

  file { "/etc/apache2/certs/":
    ensure => directory,
    owner => "root",
    group => "root",
    mode => 644,
  }

  file { "/etc/apache2/certs/humbug-self-signed.crt":
    require => File["/etc/apache2/certs/"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 640,
    source => "/root/humbug/certs/humbug-self-signed.crt",
  }

  file { "/etc/apache2/certs/humbug-self-signed.key":
    require => File["/etc/apache2/certs/"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 600,
    source => "/root/humbug/certs/humbug-self-signed.key",
  }

  file { "/etc/apache2/ports.conf":
    require => Package[apache2],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 640,
    source => "puppet:///modules/humbug/apache/ports.conf",
  }

  file { "/etc/apache2/sites-available/":
    recurse => true,
    require => Package[apache2],
    owner  => "root",
    group  => "root",
    mode => 640,
    source => "puppet:///modules/humbug/apache/sites/",
  }

  apache2site { 'humbug-default':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }
}
