class zulip_internal::base {
  include zulip::base

  $org_base_packages = [ "nagios-plugins-basic", "munin-node", "munin-plugins-extra" ]
  package { $org_base_packages: ensure => "installed" }

  file { '/home/zulip/.ssh/authorized_keys':
    ensure     => file,
    require    => File['/home/zulip/.ssh'],
    mode       => 600,
    owner      => "zulip",
    group      => "zulip",
    source     => 'puppet:///modules/zulip_internal/authorized_keys',
  }
  file { '/home/zulip/.ssh':
    ensure     => directory,
    require    => User['zulip'],
    owner      => "zulip",
    group      => "zulip",
    mode       => 600,
  }

  file { '/etc/ssh/sshd_config':
    require    => Package['openssh-server'],
    ensure     => file,
    source     => 'puppet:///modules/zulip_internal/sshd_config',
    owner      => 'root',
    group      => 'root',
    mode       => 644,
  }

  service { 'ssh':
    ensure     => running,
    subscribe  => File['/etc/ssh/sshd_config'],
  }

  file { '/root/.ssh/authorized_keys':
    ensure     => file,
    mode       => 600,
    owner      => "root",
    group      => "root",
    source     => 'puppet:///modules/zulip_internal/root_authorized_keys',
  }

  file { '/usr/local/sbin/zulip-ec2-configure-interfaces':
    ensure     => file,
    mode       => 755,
    source     => 'puppet:///modules/zulip_internal/zulip-ec2-configure-interfaces',
  }

  file { '/etc/network/if-up.d/zulip-ec2-configure-interfaces_if-up.d.sh':
    ensure     => file,
    mode       => 755,
    source     => 'puppet:///modules/zulip_internal/zulip-ec2-configure-interfaces_if-up.d.sh',
  }

  group { 'nagios':
    ensure     => present,
    gid => '1050',
  }
  user { 'nagios':
    ensure     => present,
    uid        => '1050',
    gid        => '1050',
    shell      => '/bin/bash',
    home       => '/var/lib/nagios',
    managehome => true,
  }
  file { '/var/lib/nagios/':
    ensure     => directory,
    require    => User['nagios'],
    owner      => "nagios",
    group      => "nagios",
    mode       => 600,
  }
  file { '/var/lib/nagios_state/':
    ensure     => directory,
    require    => User['nagios'],
    owner      => "nagios",
    group      => "nagios",
    mode       => 777,
  }
  file { '/var/lib/nagios/.ssh':
    ensure     => directory,
    require    => File['/var/lib/nagios/'],
    owner      => "nagios",
    group      => "nagios",
    mode       => 600,
  }
  file { '/var/lib/nagios/.ssh/authorized_keys':
    ensure     => file,
    require    => File['/var/lib/nagios/.ssh'],
    mode       => 600,
    owner      => "nagios",
    group      => "nagios",
    source     => 'puppet:///modules/zulip_internal/nagios_authorized_keys',
  }
  file { '/home/nagios':
    ensure => absent,
    force => true,
    recurse => true,
  }
  file { "/usr/lib/nagios/plugins/":
    require => Package[nagios-plugins-basic],
    recurse => true,
    purge => false,
    owner => "root",
    group => "root",
    mode => 755,
    source => "puppet:///modules/zulip_internal/nagios_plugins/",
  }
}
