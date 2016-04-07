class zulip_internal::nagios {
  include zulip_internal::apache
  include zulip::nagios

  $nagios_packages = [# Packages needed for Nagios
                      "nagios3",
                      ]
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
    source => "puppet:///modules/zulip_internal/nagios3/",
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
    source     => 'puppet:///modules/zulip_internal/pagerduty_nagios.pl',
  }

  file { '/etc/nagios3/conf.d/zulip_nagios.cfg':
    ensure     => file,
    mode       => 644,
    owner      => "root",
    group      => "root",
    source => '/root/zulip/api/integrations/nagios/zulip_nagios.cfg',
  }
  file { '/etc/nagios3/zuliprc':
    ensure     => file,
    mode       => 644,
    owner      => "root",
    group      => "root",
    source => '/root/zulip/bots/zuliprc.nagios',
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

  # I feel like installing this here is an abstraction violation; we
  # should probably move this to cron.d
  file { "/var/spool/cron/crontabs/nagios":
    require => Package[nagios3],
    owner  => "nagios",
    group  => "crontab",
    mode => 600,
    source => "puppet:///modules/zulip_internal/nagios_crontab",
  }

  # TODO: Install our API
}
