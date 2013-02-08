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
  #TODO: Need to install our trac config
}
