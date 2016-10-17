class zulip_ops::mediawiki {
  include zulip_ops::postgres_common


  $mediawiki_packages = [# Packages needed for mediawiki
                         "mediawiki",
                         "mediawiki-extensions",
                         ]
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
    source => "puppet:///modules/zulip_ops/mediawiki/LocalSettings.php",
  }

  file { '/usr/local/share/mediawiki/extensions/Auth_remoteuser.php':
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip_ops/mediawiki/Auth_remoteuser.php",
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
