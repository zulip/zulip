class zulip-internal::postgres_appdb {
  include zulip-internal::postgres_common
  include zulip::postgres_appdb

  file { "/etc/postgresql/9.1/main/pg_hba.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 640,
    source => "puppet:///modules/zulip-internal/postgresql/pg_hba.conf",
  }
}
