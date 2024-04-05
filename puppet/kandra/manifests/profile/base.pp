class kandra::profile::base {
  include zulip::profile::base
  include kandra::ksplice_uptrack
  include kandra::firewall
  include kandra::teleport::node
  include kandra::prometheus::node

  kandra::firewall_allow { 'ssh': order => '10'}
  $is_ec2 = zulipconf('machine', 'hosting_provider', 'ec2') == 'ec2'

  $org_base_packages = [
    # Standard kernel, not AWS', so ksplice works
    'linux-image-virtual',
    # Management for our systems
    'openssh-server',
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
    source => 'puppet:///modules/kandra/apt/apt.conf.d/02periodic',
  }

  file { '/etc/apt/apt.conf.d/50unattended-upgrades':
    ensure => file,
    mode   => '0644',
    source => 'puppet:///modules/kandra/apt/apt.conf.d/50unattended-upgrades',
  }
  if $facts['os']['distro']['release']['major'] == '22.04' {
    file { '/etc/needrestart/conf.d/zulip.conf':
      ensure => file,
      mode   => '0644',
      source => 'puppet:///modules/kandra/needrestart/zulip.conf',
    }
  }

  user { 'root': }
  kandra::user_dotfiles { 'root':
    home            => '/root',
    keys            => 'internal-read-only-deploy-key',
    authorized_keys => 'common',
    known_hosts     => ['github.com'],
  }

  kandra::user_dotfiles { 'zulip':
    keys            => 'internal-read-only-deploy-key',
    authorized_keys => 'common',
    known_hosts     => ['github.com'],
  }

  service { 'ssh':
    ensure => running,
  }

  include kandra::aws_tools

  if $is_ec2 {
    # EC2 hosts can use the in-VPC timeserver
    file { '/etc/chrony/chrony.conf':
      ensure  => file,
      mode    => '0644',
      source  => "puppet:///modules/kandra/chrony-${facts['os']['distro']['release']['major']}.conf",
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
  kandra::user_dotfiles { 'nagios':
    home            => '/var/lib/nagios',
    authorized_keys => true,
  }
  file { '/home/nagios':
    ensure  => absent,
    force   => true,
    recurse => true,
  }
}
