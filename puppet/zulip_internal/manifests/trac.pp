class zulip_internal::trac {
  include zulip_internal::base
  include zulip_internal::apache
  include zulip_internal::mediawiki

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
    source => "puppet:///modules/zulip_internal/trac.ini",
    require => User['zulip'],
  }
  file { "/home/zulip/trac/cgi-bin/":
    recurse => true,
    owner => "zulip",
    group => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_internal/trac/cgi-bin/",
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
    source   => 'puppet:///modules/zulip_internal/postgresql/40-postgresql.conf.trac',
  }

  file { "/etc/postgresql/9.1/main/postgresql.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 644,
    source => "puppet:///modules/zulip_internal/postgresql/postgresql.conf.trac",
  }
}
