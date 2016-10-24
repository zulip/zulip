class zulip_ops::postgres_appdb {
  include zulip_ops::postgres_common
  include zulip::postgres_appdb_base

  file { "/etc/postgresql/${zulip::base::postgres_version}/main/pg_hba.conf":
    require => Package["postgresql-${zulip::base::postgres_version}"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 640,
    source => "puppet:///modules/zulip_ops/postgresql/pg_hba.conf",
  }
}
