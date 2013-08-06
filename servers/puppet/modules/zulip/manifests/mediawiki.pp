class zulip::mediawiki {
  class { 'zulip::postgres-common': }


  $mediawiki_packages = [ "mediawiki", "mediawiki-extensions" ]
  package { $mediawiki_packages: ensure => "installed" }

  apache2site {'mediawiki':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }

  file { '/etc/mediawiki/LocalSettings.php':
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/mediawiki/LocalSettings.php",
  }

  file { '/usr/local/share/mediawiki/extensions/Auth_remoteuser.php':
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/mediawiki/Auth_remoteuser.php",
  }

  file { '/etc/mediawiki-extensions/extensions-available/Auth_remoteuser.php':
    ensure => 'link',
    target => '/usr/local/share/mediawiki/extensions/Auth_remoteuser.php',
  }
  file { '/etc/mediawiki-extensions/extensions-enabled/Auth_remoteuser.php':
    ensure => 'link',
    target => '../extensions-available/Auth_remoteuser.php',
  }
}
