# @summary Included only by classes that can be deployed.
#
# This class should only be included by classes that are intended to
# be able to be deployed on their own host.
class zulip::profile::base {
  include zulip::timesync
  include zulip::common
  case $::os['family'] {
    'Debian': {
      include zulip::apt_repository
    }
    'RedHat': {
      include zulip::yum_repository
    }
    default: {
      fail('osfamily not supported')
    }
  }
  case $::os['family'] {
    'Debian': {
      $base_packages = [
        # Basics
        'python3',
        'python3-yaml',
        'puppet',
        'git',
        'curl',
        'jq',
        'procps',
        # Used to read /etc/zulip/zulip.conf for `zulipconf` Puppet function
        'crudini',
        # Used for tools like sponge
        'moreutils',
        # Nagios monitoring plugins
        $zulip::common::nagios_plugins,
        # Required for using HTTPS in apt repositories.
        'apt-transport-https',
        # Needed for the cron jobs installed by Puppet
        'cron',
      ]
    }
    'RedHat': {
      $base_packages = [
        'python3',
        'python3-pyyaml',
        'puppet',
        'git',
        'curl',
        'jq',
        'crudini',
        'moreutils',
        'nmap-ncat',
        'nagios-plugins',  # there is no dummy package on CentOS 7
        'cronie',
      ]
    }
    default: {
      fail('osfamily not supported')
    }
  }
  package { $base_packages: ensure => installed }

  group { 'zulip':
    ensure => present,
  }

  user { 'zulip':
    ensure     => present,
    require    => Group['zulip'],
    gid        => 'zulip',
    shell      => '/bin/bash',
    home       => '/home/zulip',
    managehome => true,
  }

  file { '/etc/zulip':
    ensure => directory,
    mode   => '0644',
    owner  => 'zulip',
    group  => 'zulip',
    links  => follow,
  }
  file { ['/etc/zulip/zulip.conf', '/etc/zulip/settings.py']:
    ensure  => file,
    require => File['/etc/zulip'],
    mode    => '0644',
    owner   => 'zulip',
    group   => 'zulip',
  }
  file { '/etc/zulip/zulip-secrets.conf':
    ensure  => file,
    require => File['/etc/zulip'],
    mode    => '0640',
    owner   => 'zulip',
    group   => 'zulip',
  }

  file { '/etc/security/limits.conf':
    ensure => file,
    mode   => '0640',
    owner  => 'root',
    group  => 'root',
    source => 'puppet:///modules/zulip/limits.conf',
  }

  # This directory is written to by cron jobs for reading by Nagios
  file { '/var/lib/nagios_state/':
    ensure => directory,
    group  => 'zulip',
    mode   => '0774',
  }

  file { '/var/log/zulip':
    ensure => directory,
    owner  => 'zulip',
    group  => 'zulip',
    mode   => '0640',
  }

  file { "${zulip::common::nagios_plugins_dir}/zulip_base":
    require => Package[$zulip::common::nagios_plugins],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/nagios_plugins/zulip_base',
  }
}
