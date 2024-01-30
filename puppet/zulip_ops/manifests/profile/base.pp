class zulip_ops::profile::base {
  include zulip::profile::base
  include zulip_ops::munin_node
  include zulip_ops::ksplice_uptrack
  include zulip_ops::firewall
  include zulip_ops::teleport::node
  include zulip_ops::prometheus::node

  zulip_ops::firewall_allow { 'ssh': order => '10'}
  $is_ec2 = zulipconf('machine', 'hosting_provider', 'ec2') == 'ec2'

  $org_base_packages = [
    # Standard kernel, not AWS', so ksplice works
    'linux-image-virtual',
    # Management for our systems
    'openssh-server',
    'mosh',
    # package management
    'aptitude',
    # SSL certificates
    'certbot',
    # For managing our current Debian packages
    'debian-goodies',
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
  zulip::safepackage { $org_base_packages: ensure => installed }

  # Uninstall the AWS kernel, but only after we install the usual one
  package { ['linux-image-aws', 'linux-headers-aws', 'linux-aws-*', 'linux-image-*-aws', 'linux-modules-*-aws']:
    ensure  => absent,
    require => Package['linux-image-virtual'],
  }

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
  if $::os['distro']['release']['major'] == '22.04' {
    file { '/etc/needrestart/conf.d/zulip.conf':
      ensure => file,
      mode   => '0644',
      source => 'puppet:///modules/zulip_ops/needrestart/zulip.conf',
    }
  }

  user { 'root': }
  zulip_ops::user_dotfiles { 'root':
    home => '/root',
    keys => 'common',
  }

  zulip_ops::user_dotfiles { 'zulip':
    keys => 'common',
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


  include zulip_ops::aws_tools

  if $is_ec2 {
    # Non-EC2 (e.g. CZO) don't have the private commit that adds these
    # zulip_ops files.
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

    # EC2 hosts can use the in-VPC timeserver
    file { '/etc/chrony/chrony.conf':
      ensure  => file,
      mode    => '0644',
      source  => 'puppet:///modules/zulip_ops/chrony.conf',
      require => Package['chrony'],
      notify  => Service['chrony'],
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
  file { '/var/lib/nagios':
    ensure  => directory,
    require => User['nagios'],
    owner   => 'nagios',
    group   => 'nagios',
    mode    => '0700',
  }
  zulip_ops::user_dotfiles { 'nagios': home => '/var/lib/nagios' }
  file { '/home/nagios':
    ensure  => absent,
    force   => true,
    recurse => true,
  }
}
