class humbug::postgres-master {
  class { 'humbug::postgres-common': }

  $master_packages = [ "xfsprogs", "mdadm", ]
  package { $master_packages: ensure => "installed" }

  # We bundle a bunch of other sysctl parameters into 40-postgresql.conf
  file { '/etc/sysctl.d/30-postgresql-shm.conf':
    ensure => absent,
  }

  file { '/etc/sysctl.d/40-postgresql.conf':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => 644,
    source   => 'puppet:///modules/humbug/postgresql/40-postgresql.conf.master',
  }

  file { "/etc/postgresql/9.1/main/postgresql.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 644,
    source => "puppet:///modules/humbug/postgresql/postgresql.conf.master",
  }

  file { "/root/setup_disks.sh":
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => 744,
    source => 'puppet:///modules/humbug/postgresql/setup_disks.sh',
  }

  exec { "setup_disks":
    command => "/root/setup_disks.sh",
    require => Package["postgresql-9.1", "xfsprogs", "mdadm"],
    creates => "/dev/md0"
  }
}
