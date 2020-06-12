class zulip_ops::postgres_master {
  include zulip_ops::base
  include zulip_ops::postgres_appdb

  file { '/etc/sysctl.d/40-postgresql.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/postgresql/40-postgresql.conf.master',
  }
}
