class zulip_ops::nagios {
  include zulip_ops::base
  include zulip_ops::apache
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
    source => "puppet:///modules/zulip_ops/nagios3/",
    notify => Service["nagios3"],
  }

  $nagios_format_users = join($zulip_ops::base::users, ",")
  file { "/etc/nagios3/cgi.cfg":
    require => Package[nagios3],
    owner  => "root",
    group  => "root",
    mode => 644,
    content => template("zulip_ops/nagios3/cgi.cfg.template.erb"),
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
    source     => 'puppet:///modules/zulip_ops/pagerduty_nagios.pl',
  }

  file { [ '/etc/nagios3/conf.d/extinfo_nagios2.cfg',
           '/etc/nagios3/conf.d/services_nagios2.cfg',
           '/etc/nagios3/conf.d/contacts_nagios2.cfg',
           '/etc/nagios3/conf.d/hostgroups_nagios2.cfg',
           '/etc/nagios3/conf.d/localhost_nagios2.cfg',
           ]:
    ensure     => absent,
  }

  file { '/etc/nagios3/conf.d/zulip_nagios.cfg':
    ensure     => file,
    mode       => 644,
    owner      => "root",
    group      => "root",
    source => '/root/zulip/api/integrations/nagios/zulip_nagios.cfg',
    notify => Service["nagios3"],
  }

  $hosts = $zulip_ops::base::hosts
  file { '/etc/nagios3/conf.d/zulip_autossh.cfg':
    ensure     => file,
    mode       => 644,
    owner      => "root",
    group      => "root",
    content => template('zulip_ops/nagios_autossh.template.erb'),
    notify => Service["nagios3"],
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
    source => "puppet:///modules/zulip_ops/nagios_crontab",
  }

  # TODO: Install our API
}
