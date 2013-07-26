class humbug::postgres-appdb {
  class { 'humbug::base': }
  class { 'humbug::postgres-common': }

  file { "/etc/postgresql/9.1/main/pg_hba.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 640,
    source => "puppet:///modules/humbug/postgresql/pg_hba.conf",
  }

  file { "/usr/share/postgresql/9.1/tsearch_data/humbug_english.stop":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/humbug/postgresql/humbug_english.stop",
  }

}
