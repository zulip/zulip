class humbug::loadbalancer {
  class { 'humbug::base': }
  class { 'humbug::nginx': }

  file { "/etc/nginx/humbug-include/":
    require => Package[nginx],
    recurse => true,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/nginx/humbug-include/",
    notify => Service["nginx"],
  }

  file { "/etc/nginx/sites-available/loadbalancer":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/nginx/sites-available/loadbalancer",
  }

  file { "/etc/motd":
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/motd.lb0",
  }

  file { '/etc/nginx/sites-enabled/loadbalancer':
    ensure => 'link',
    target => '/etc/nginx/sites-available/loadbalancer',
  }

}
