# For any system using nginx (currently just app frontends)
class humbug::nginx {
  $web_packages = [ "nginx", ]
  package { $web_packages: ensure => "installed" }

  file { "/etc/nginx/nginx.conf":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/nginx/nginx.conf",
  }

  file { "/etc/nginx/sites-enabled/default":
    notify => Service["nginx"],
    ensure => absent,
  }

  service { 'nginx':
    ensure     => running,
    subscribe  => File['/etc/nginx/nginx.conf'],
  }
}

