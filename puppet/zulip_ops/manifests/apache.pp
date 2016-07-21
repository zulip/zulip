class zulip_ops::apache {
  $apache_packages = [# Needed to run Apache with WSGI
                      "apache2",
                      "libapache2-mod-wsgi",
                      ]
  package { $apache_packages: ensure => "installed" }

  apache2mod { [ "headers", "proxy", "proxy_http", "rewrite", "auth_digest", "ssl" ]:
    ensure  => present,
    require => Package['apache2'],
  }

  file { "/etc/apache2/users/":
    require => Package['apache2'],
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
    source => "puppet:///modules/zulip_ops/apache/users",
  }

  file { "/etc/apache2/certs/":
    require => Package['apache2'],
    ensure => directory,
    owner => "root",
    group => "root",
    mode => 644,
  }

  file { "/etc/apache2/ports.conf":
    require => Package[apache2],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 640,
    source => "puppet:///modules/zulip_ops/apache/ports.conf",
  }

  file { "/etc/apache2/sites-available/":
    ensure => directory,
    require => Package[apache2],
    owner  => "root",
    group  => "root",
    mode => 640,
  }
}
