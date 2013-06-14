class humbug::wiki {
  class { 'humbug::apache': }
  class { 'humbug::supervisor': }

  $wiki_packages = [ "gitit", ]
  package { $wiki_packages: ensure => "installed" }

  apache2site { 'wiki':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }

  group { 'wiki':
    ensure     => present,
    gid        => '1100',
  }
  user { 'wiki':
    ensure     => present,
    uid        => '1100',
    gid        => '1100',
    require    => Group['wiki'],
    shell      => '/bin/bash',
    home       => '/home/wiki',
    managehome => true,
  }

  file { "/home/wiki/wiki/":
    recurse => true,
    owner  => "wiki",
    group  => "wiki",
    source => "puppet:///modules/humbug/wiki",
    require => User['wiki'],
  }
  file { '/etc/supervisor/conf.d/gitit.conf':
    require => Package['supervisor'],
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => 640,
    source  => "puppet:///modules/humbug/supervisord/conf.d/gitit.conf",
    notify  => Service['supervisor'],
  }
}
