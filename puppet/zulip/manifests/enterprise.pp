class zulip::enterprise {
  include zulip::base
  include zulip::app_frontend
  include zulip::postgres_appdb
  include zulip::camo

  apt::key {"A529EF65":
    source  =>  "http://apt.zulip.com/enterprise.asc",
  }

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
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }

  file { '/etc/postgresql/9.1/main/postgresql.conf.template':
    require => Package[postgres],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode   => 644,
    source => "puppet:///modules/zulip/postgresql/postgresql.conf.template"
  }

  $total_memory = regsubst(file('/proc/meminfo'), '^.*MemTotal:\s*(\d+) kB.*$', '\1', 'M') * 1024
  $half_memory = $total_memory / 2

  exec { 'pgtune':
    require => Package[pgtune],
    # Let Postgres use half the memory on the machine
    command => "pgtune -T Web -M $half_memory -i /etc/postgresql/9.1/main/postgresql.conf.template -o /etc/postgresql/9.1/main/postgresql.conf",
    refreshonly => true,
    subscribe => File['/etc/postgresql/9.1/main/postgresql.conf.template']
  }

  exec { 'pg_ctlcluster 9.1 main restart':
    refreshonly => true,
    subscribe => Exec['pgtune']
  }
}
