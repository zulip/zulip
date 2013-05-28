class humbug::staging_app_frontend {
  class { 'humbug::app_frontend': }

  file { "/etc/nginx/sites-available/humbug-staging":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/nginx/sites-available/humbug-staging",
  }
  file { '/etc/nginx/sites-enabled/humbug-staging':
    ensure => 'link',
    target => '/etc/nginx/sites-available/humbug-staging',
  }

}
