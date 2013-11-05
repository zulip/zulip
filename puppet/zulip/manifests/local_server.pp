class zulip::local_server {
  include zulip::base
  include zulip::app_frontend
  include zulip::postgres_appdb

  # This should be migrated over to app_frontend, once validated as functional
  # on app servers.
  package { "nodejs": ensure => installed }

  file { "/etc/nginx/sites-available/zulip-local":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/sites-available/zulip-local",
  }
  file { '/etc/nginx/sites-enabled/zulip-local':
    ensure => 'link',
    target => '/etc/nginx/sites-available/zulip-local',
  }
  file { '/home/zulip/deployments/current':
    ensure => 'link',
    target => '/home/zulip/zulip',
  }
  file { '/home/zulip/prod-static':
    ensure => 'link',
    target => '/home/zulip/deployments/current/prod-static/serve',
  }

  file { '/etc/postgresql/9.1/main/postgresql.conf.template':
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode   => 644,
    source => "puppet:///modules/zulip/postgresql/postgresql.conf.template"
  }

  exec { 'pgtune':
    command => 'pgtune -T Web -i /etc/postgresql/9.1/main/postgresql.conf.template -o /etc/postgresql/9.1/main/postgresql.conf',
    refreshonly => true,
    subscribe => File['/etc/postgresql/9.1/main/postgresql.conf.template']
  }

  exec { 'pg_ctlcluster 9.1 main restart':
    refreshonly => true,
    subscribe => Exec['pgtune']
  }
}
