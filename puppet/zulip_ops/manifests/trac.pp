class zulip_ops::trac {
  include zulip_ops::base
  include zulip_ops::apache
  include zulip_ops::mediawiki

  $trac_packages = [# Packages needed to run trac
                    "trac",
                    ]
  package { $trac_packages: ensure => "installed" }

  apache2site { 'trac':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }
  file { "/home/zulip/trac/conf/trac.ini":
    owner  => "zulip",
    group  => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_ops/trac.ini",
    require => User['zulip'],
  }
  file { "/home/zulip/trac/cgi-bin/":
    recurse => true,
    owner => "zulip",
    group => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_ops/trac/cgi-bin/",
  }
  file { '/home/zulip/trac/plugins/zulip_trac.py':
    ensure => 'link',
    target => '/home/zulip/zulip/api/integrations/trac/zulip_trac.py',
  }
  file { '/home/zulip/trac/plugins/zulip_trac_config.py':
    ensure => 'link',
    target => '/home/zulip/zulip/bots/zulip_trac_config.py',
  }
  # TODO: Add downloading and installing trac at /home/zulip/trac

  file { '/etc/sysctl.d/40-postgresql.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => 644,
    source   => 'puppet:///modules/zulip_ops/postgresql/40-postgresql.conf.trac',
  }

  file { "/etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf":
    require => Package["postgresql-${zulip::base::postgres_version}"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 644,
    source => "puppet:///modules/zulip_ops/postgresql/postgresql.conf.trac",
  }
}
