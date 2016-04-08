class zulip_internal::base {
  include zulip::base

  $org_base_packages = [# Management for our systems
                        "openssh-server",
                        "mosh",
                        # Monitoring
                        "munin-node",
                        "munin-plugins-extra" ,
                        # Security
                        "iptables-persistent",
                        # For managing our current Debian packages
                        "debian-goodies",
                        # For our EC2 network setup script
                        "python-netifaces",
                        # Popular editors
                        "vim",
                        "emacs23-nox",
                        "puppet-el",
                        # Prevent accidental reboots
                        "molly-guard",
                        # Useful tools in a production environment
                        "screen",
                        "strace",
                        "moreutils",
                        "host",
                        "git",
                         ]
  package { $org_base_packages: ensure => "installed" }

  apt::source {'zulip':
    location    => 'http://apt.zulip.net/ops',
    release     => 'wheezy',
    repos       => 'main',
    key         => 'E5FB045CA79AA8FC25FDE9F3B4F81D07A529EF65',
    key_source  => 'https://zulip.com/dist/keys/ops.asc',
    pin         => '995',
    include_src => true,
  }

  file { '/etc/apt/apt.conf.d/02periodic':
    ensure     => file,
    mode       => 644,
    source     => 'puppet:///modules/zulip_internal/apt/apt.conf.d/02periodic',
  }

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
  file { '/etc/iptables/rules.v4':
    ensure     => file,
    mode       => 600,
    content    => template('zulip_internal/iptables/rules.v4.erb'),
    require    => Package['iptables-persistent'],
  }
  service { 'iptables-persistent':
    ensure     => running,

    # Because there is no running process for this service, the normal status
    # checks fail.  Because puppet then thinks the service has been manually
    # stopped, it won't restart it.  This fake status command will trick puppet
    # into thinking the service is *always* running (which in a way it is, as
    # iptables is part of the kernel.)
    hasstatus => true,
    status => "/bin/true",

    # Under Debian, the "restart" parameter does not reload the rules, so tell
    # Puppet to fall back to stop/start, which does work.
    hasrestart => false,

    subscribe  => File['/etc/iptables/rules.v4'],
  }
}
