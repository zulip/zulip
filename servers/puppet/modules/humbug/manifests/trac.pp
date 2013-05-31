class humbug::trac {
  class { 'humbug::base': }
  class { 'humbug::apache': }

  $trac_packages = [ "trac", ]
  package { $trac_packages: ensure => "installed" }

  apache2site { 'trac':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }
  file { "/home/humbug/trac/conf/trac.ini":
    owner  => "humbug",
    group  => "humbug",
    source => "puppet:///modules/humbug/trac.ini",
    require => User['humbug'],
  }
  file { '/home/humbug/trac/plugins/humbug_trac.py':
    ensure => 'link',
    target => '/home/humbug/humbug/api/integrations/trac/humbug_trac.py',
  }
  file { '/home/humbug/trac/plugins/humbug_trac_config.py':
    ensure => 'link',
    target => '/home/humbug/humbug/bots/humbug_trac_config.py',
  }
  # TODO: Add downloading and installing trac at /home/humbug/trac
}
