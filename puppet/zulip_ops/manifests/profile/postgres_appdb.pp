class zulip_ops::profile::postgres_appdb {
  include zulip_ops::profile::base
  include zulip::profile::postgresql
  include zulip::postgresql_backups

  $common_packages = ['xfsprogs']
  package { $common_packages: ensure => 'installed' }

  file { '/etc/sysctl.d/40-postgresql.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/postgresql/40-postgresql.conf',
  }
  exec { 'sysctl_p':
    command     => '/sbin/sysctl -p /etc/sysctl.d/40-postgresql.conf',
    subscribe   => File['/etc/sysctl.d/40-postgresql.conf'],
    refreshonly => true,
  }

  file { '/root/setup_disks.sh':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0744',
    source => 'puppet:///modules/zulip_ops/postgresql/setup_disks.sh',
  }
  exec { 'setup_disks':
    command => '/root/setup_disks.sh',
    require => Package["postgresql-${zulip::postgresql_common::version}", 'xfsprogs'],
    unless  => 'test $(readlink /var/lib/postgresql) = "/srv/postgresql/" -a -d /srv/postgresql',
  }

  file { "${zulip::postgresql_base::postgres_confdir}/pg_hba.conf":
    ensure  => file,
    require => Package["postgresql-${zulip::postgresql_common::version}"],
    owner   => 'postgres',
    group   => 'postgres',
    mode    => '0640',
    source  => 'puppet:///modules/zulip_ops/postgresql/pg_hba.conf',
  }
}
