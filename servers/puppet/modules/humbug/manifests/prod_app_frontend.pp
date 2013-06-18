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

  file { [ "/srv/www/", "/srv/www/dist/", "/srv/www/dist/api",
           "/srv/www/dist/apps/", "/srv/www/dist/apps/mac/" ]:
    ensure => "directory",
    owner      => "humbug",
    group      => "humbug",
    mode       => 644,
  }

  file { "/srv/www/dist/apps/mac/sparkle.xml":
    ensure => file,
    require    => File['/srv/www/dist/apps/mac/'],
    owner  => "humbug",
    group  => "humbug",
    mode => 644,
    source => "puppet:///modules/humbug/sparkle/sparkle.xml",
  }
  file { "/srv/www/dist/apps/mac/sparkle-changelog.html":
    ensure => file,
    require    => File['/srv/www/dist/apps/mac/'],
    owner  => "humbug",
    group  => "humbug",
    mode => 644,
    source => "puppet:///modules/humbug/sparkle/sparkle-changelog.html",
  }
}
