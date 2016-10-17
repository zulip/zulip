class zulip_ops::postgres_master {
  include zulip_ops::base
  include zulip_ops::postgres_appdb

  $master_packages = [# Packages needed for disk + RAID configuration
                      "xfsprogs",
                      "mdadm",
                      ]
  package { $master_packages: ensure => "installed" }

  file { '/etc/sysctl.d/40-postgresql.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => 644,
    source   => 'puppet:///modules/zulip_ops/postgresql/40-postgresql.conf.master',
  }

  file { "/etc/postgresql/${zulip::base::postgres_version}/main/postgresql.conf":
    require => Package["postgresql-${zulip::base::postgres_version}"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 644,
    source => "puppet:///modules/zulip_ops/postgresql/postgresql.conf.master",
  }

  file { "/root/setup_disks.sh":
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => 744,
    source => 'puppet:///modules/zulip_ops/postgresql/setup_disks.sh',
  }

  exec { "setup_disks":
    command => "/root/setup_disks.sh",
    require => Package["postgresql-${zulip::base::postgres_version}", "xfsprogs", "mdadm"],
    creates => "/dev/md0"
  }
}
