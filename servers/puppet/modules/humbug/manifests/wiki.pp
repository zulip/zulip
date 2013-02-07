class humbug::wiki {
  class { 'humbug::base': }
  class { 'humbug::apache': }

  $wiki_packages = [ "gitit", ]
  package { $wiki_packages: ensure => "installed" }

  group { 'wiki':
    ensure     => present,
    gid        => '1100',
  }

  apache2site { 'wiki':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
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
  }
}
