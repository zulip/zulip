class humbug::prod_app_frontend {
  class { 'humbug::app_frontend': }

  file { "/etc/nginx/sites-available/humbug":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/nginx/sites-available/humbug",
  }
  file { '/etc/nginx/sites-enabled/humbug':
    ensure => 'link',
    target => '/etc/nginx/sites-available/humbug',
  }


  # TODO: Setup the API distribution directory at /srv/www/dist/api/.

}
