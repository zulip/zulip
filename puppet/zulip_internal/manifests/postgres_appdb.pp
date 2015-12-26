class zulip_internal::postgres_appdb {
  include zulip_internal::postgres_common
  include zulip::postgres_appdb_base

  file { "/etc/postgresql/9.1/main/pg_hba.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 640,
    source => "puppet:///modules/zulip_internal/postgresql/pg_hba.conf",
  }
}
