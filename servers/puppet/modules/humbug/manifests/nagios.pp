class humbug::nagios {
  class { 'humbug::base': }
  class { 'humbug::apache': }

  $nagios_packages = [ "nagios3", "munin", "autossh" ]
  package { $nagios_packages: ensure => "installed" }

  apache2site { 'nagios':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }

  file { "/etc/nagios3/":
    recurse => true,
    purge => false,
    require => Package[nagios3],
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/nagios3/",
    notify => Service["nagios3"],
  }

  service { "nagios3":
    ensure => running,
  }

  file { '/usr/local/bin/pagerduty_nagios.pl':
    ensure     => file,
    mode       => 755,
    owner      => "root",
    group      => "root",
    source     => 'puppet:///modules/humbug/pagerduty_nagios.pl',
  }

  exec { "fix_nagios_permissions":
    command => "dpkg-statoverride --update --add nagios www-data 2710 /var/lib/nagios3/rw",
    unless => "bash -c 'ls -ld /var/lib/nagios3/rw | grep ^drwx--s--- -q'",
    notify => Service["nagios3"],
  }
  exec { "fix_nagios_permissions2":
    command => "dpkg-statoverride --update --add nagios nagios 751 /var/lib/nagios3",
    unless => "bash -c 'ls -ld /var/lib/nagios3 | grep ^drwxr-x--x -q'",
    notify => Service["nagios3"],
  }

  # TODO: Install our API
  # TODO: Install the pagerduty_nagios cron job /var/spool/cron/crontabs/nagios

  # TODO: Add munin configuration
}
