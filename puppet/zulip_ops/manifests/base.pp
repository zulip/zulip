class zulip_ops::base {
  include zulip::base
  include zulip_ops::munin_node

  $org_base_packages = [# Management for our systems
    'openssh-server',
    'mosh',
    # package management
    'aptitude',
    # SSL Certificates
    'certbot',
    # Security
    'iptables-persistent',
    # For managing our current Debian packages
    'debian-goodies',
    # Needed for zulip-ec2-configure-network-interfaces
    'python3-boto3',
    'python3-netifaces',
    # Popular editors
    'vim',
    'emacs-nox',
    # Prevent accidental reboots
    'molly-guard',
    # Useful tools in a production environment
    'screen',
    'strace',
    'bind9-host',
    'git',
    'nagios-plugins-contrib',
  ]
  zulip::safepackage { $org_base_packages: ensure => 'installed' }

  # Add system users here
  $users = []

  file { '/etc/apt/apt.conf.d/02periodic':
    ensure => file,
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/apt/apt.conf.d/02periodic',
  }

  file { '/etc/apt/apt.conf.d/50unattended-upgrades':
    ensure => file,
    mode   => '0644',
    source => 'puppet:///modules/zulip_ops/apt/apt.conf.d/50unattended-upgrades',
  }

  file { '/home/zulip/.ssh':
    ensure  => directory,
    require => User['zulip'],
    owner   => 'zulip',
    group   => 'zulip',
    mode    => '0600',
  }

  # Clear /etc/update-motd.d, to fix load problems with Nagios
  # caused by Ubuntu's default MOTD tools for things like "checking
  # for the next release" being super slow.
  file { '/etc/update-motd.d':
    ensure  => directory,
    recurse => true,
    purge   => true,
  }

  file { '/etc/pam.d/common-session':
    ensure  => file,
    require => Package['openssh-server'],
    source  => 'puppet:///modules/zulip_ops/common-session',
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
  }

  service { 'ssh':
    ensure     => running,
  }

  file { '/etc/ssh/sshd_config':
    ensure  => file,
    require => Package['openssh-server'],
    source  => 'puppet:///modules/zulip_ops/sshd_config',
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['ssh'],
  }

  file { '/root/.emacs':
    ensure => file,
    mode   => '0600',
    owner  => 'root',
    group  => 'root',
    source => 'puppet:///modules/zulip_ops/dot_emacs.el',
  }

  file { '/home/zulip/.emacs':
    ensure  => file,
    mode    => '0600',
    owner   => 'zulip',
    group   => 'zulip',
    source  => 'puppet:///modules/zulip_ops/dot_emacs.el',
    require => User['zulip'],
  }

  $hosting_provider = zulipconf('machine', 'hosting_provider', 'ec2')
  if $hosting_provider == 'ec2' {
    # This conditional block is for for whether it's not
    # chat.zulip.org, which uses a different hosting provider.
    package { 'dhcpcd5':
      ensure => 'installed',
    }
    file { '/root/.ssh/authorized_keys':
      ensure => file,
      mode   => '0600',
      owner  => 'root',
      group  => 'root',
      source => 'puppet:///modules/zulip_ops/root_authorized_keys',
    }
    file { '/home/zulip/.ssh/authorized_keys':
      ensure  => file,
      require => File['/home/zulip/.ssh'],
      mode    => '0600',
      owner   => 'zulip',
      group   => 'zulip',
      source  => 'puppet:///modules/zulip_ops/authorized_keys',
    }
    file { '/var/lib/nagios/.ssh/authorized_keys':
      ensure  => file,
      require => File['/var/lib/nagios/.ssh'],
      mode    => '0600',
      owner   => 'nagios',
      group   => 'nagios',
      source  => 'puppet:///modules/zulip_ops/nagios_authorized_keys',
    }
  }

  if $hosting_provider == 'ec2' {
    file { '/usr/local/sbin/zulip-ec2-configure-interfaces':
      ensure => file,
      mode   => '0755',
      source => 'puppet:///modules/zulip_ops/zulip-ec2-configure-interfaces',
    }

    file { '/etc/network/if-up.d/zulip-ec2-configure-interfaces_if-up.d.sh':
      ensure => file,
      mode   => '0755',
      source => 'puppet:///modules/zulip_ops/zulip-ec2-configure-interfaces_if-up.d.sh',
    }
  }

  group { 'nagios':
    ensure => present,
    gid    => '1050',
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
    ensure  => directory,
    require => User['nagios'],
    owner   => 'nagios',
    group   => 'nagios',
    mode    => '0600',
  }
  file { '/var/lib/nagios/.ssh':
    ensure  => directory,
    require => File['/var/lib/nagios/'],
    owner   => 'nagios',
    group   => 'nagios',
    mode    => '0600',
  }
  file { '/home/nagios':
    ensure  => absent,
    force   => true,
    recurse => true,
  }

  file { '/etc/iptables/rules.v4':
    ensure  => file,
    mode    => '0600',
    content => template('zulip_ops/iptables/rules.v4.erb'),
    require => Package['iptables-persistent'],
  }
  service { 'netfilter-persistent':
    ensure     => running,

    # Because there is no running process for this service, the normal status
    # checks fail.  Because puppet then thinks the service has been manually
    # stopped, it won't restart it.  This fake status command will trick puppet
    # into thinking the service is *always* running (which in a way it is, as
    # iptables is part of the kernel.)
    hasstatus  => true,
    status     => '/bin/true',

    # Under Debian, the "restart" parameter does not reload the rules, so tell
    # Puppet to fall back to stop/start, which does work.
    hasrestart => false,

    require    => Package['iptables-persistent'],
    subscribe  => File['/etc/iptables/rules.v4'],
  }
}
