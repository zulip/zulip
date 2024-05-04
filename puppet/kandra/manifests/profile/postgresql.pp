class kandra::profile::postgresql inherits kandra::profile::base {

  include zulip::profile::postgresql
  include kandra::teleport::db
  include kandra::prometheus::postgresql

  package { ['xfsprogs', 'nvme-cli']: ensure => installed }

  kandra::firewall_allow{ 'postgresql': }

  zulip::sysctl { 'postgresql-swappiness':
    key   => 'vm.swappiness',
    value => '0',
  }
  zulip::sysctl { 'postgresql-overcommit':
    key   => 'vm.overcommit_memory',
    value => '2',
  }

  file { '/root/setup_disks.sh':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0744',
    source => 'puppet:///modules/kandra/postgresql/setup_disks.sh',
  }
  exec { 'setup_disks':
    command => '/root/setup_disks.sh',
    # We need to not have started installing the non-AWS kernel, so
    # the xfs module gets installed for the running kernel, and we can
    # mount it.
    before  => Package['linux-image-virtual'],
    require => Package["postgresql-${zulip::postgresql_common::version}", 'xfsprogs', 'nvme-cli'],
    unless  => 'test /var/lib/postgresql/ -ef /srv/data/postgresql/',
  }

  # This is the second stage, after secrets are configured
  $replication_primary = zulipconf('postgresql', 'replication_primary', undef)
  if $replication_primary != undef {
      file { '/root/setup_data.sh':
        ensure => file,
        owner  => 'root',
        group  => 'root',
        mode   => '0744',
        source => 'puppet:///modules/kandra/postgresql/setup_data.sh',
      }
      exec { 'setup_data':
        command => '/root/setup_data.sh',
        require => [File['/usr/local/bin/env-wal-g'], Exec['setup_disks']],
        unless  => "test -d /srv/data/postgresql/${zulip::postgresql_common::version}/main",
        timeout => 0,
        notify  => Exec[$zulip::postgresql_base::postgresql_restart],
      }
  }

  file { "${zulip::postgresql_base::postgresql_confdir}/pg_hba.conf":
    ensure  => file,
    require => Package["postgresql-${zulip::postgresql_common::version}"],
    notify  => Exec[$zulip::postgresql_base::postgresql_restart],
    owner   => 'postgres',
    group   => 'postgres',
    mode    => '0640',
    source  => 'puppet:///modules/kandra/postgresql/pg_hba.conf',
  }
}
