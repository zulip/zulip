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

  # This one will probably fail most of the time
  exec {'give_nagios_user_access':
    # lint:ignore:140chars
    command => "bash -c \"su postgres -c 'psql -v ON_ERROR_STOP=1 zulip < /usr/share/postgresql/${zulip::base::postgres_version}/zulip_nagios_setup.sql' && touch /usr/share/postgresql/${zulip::base::postgres_version}/zulip_nagios_setup.sql.applied\"",
    # lint:endignore
    creates => "/usr/share/postgresql/${zulip::base::postgres_version}/zulip_nagios_setup.sql.applied",
    require => Package["postgresql-${zulip::base::postgres_version}"],
  }
}
