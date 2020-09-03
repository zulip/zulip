class zulip::base {
  include zulip::common
  case $::osfamily {
    'debian': {
      $release_name = $::operatingsystemrelease ? {
        # Debian releases
        /^7\.[0-9]*$/  => 'wheezy',
        /^8\.[0-9]*$/  => 'jessie',
        /^9\.[0-9]*$/  => 'stretch',
        /^10\.[0-9]*$/ => 'buster',
        # Ubuntu releases
        '12.04' => 'precise',
        '14.04' => 'trusty',
        '15.04' => 'vivid',
        '15.10' => 'wily',
        '16.04' => 'xenial',
        '18.04' => 'bionic',
        '20.04' => 'focal',
      }
      $base_packages = [
        # Accurate time is essential
        'ntp',
        # Used in scripts including install-yarn.sh
        'curl',
        'wget',
        # Used to read /etc/zulip/zulip.conf for `zulipconf` puppet function
        'crudini',
        # Used for tools like sponge
        'moreutils',
        # Nagios monitoring plugins
        $zulip::common::nagios_plugins,
        # Required for using HTTPS in apt repositories.
        'apt-transport-https',
        # Needed for the cron jobs installed by puppet
        'cron',
      ]
    }
    'redhat': {
      $release_name = "${::operatingsystem}${::operatingsystemmajrelease}"
      $base_packages = [
        'ntp',
        'curl',
        'wget',
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
  package { $base_packages: ensure => 'installed' }

  $postgres_version = zulipconf('postgresql', 'version', undef)

  $normal_queues = [
    'deferred_work',
    'digest_emails',
    'email_mirror',
    'embed_links',
    'embedded_bots',
    'error_reports',
    'invites',
    'email_senders',
    'missedmessage_emails',
    'missedmessage_mobile_notifications',
    'outgoing_webhooks',
    'signups',
    'user_activity',
    'user_activity_interval',
    'user_presence',
  ]

  $total_memory_mb = Integer($::memorysize_mb);

  group { 'zulip':
    ensure     => present,
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
    ensure => 'directory',
    mode   => '0644',
    owner  => 'zulip',
    group  => 'zulip',
    links  => 'follow',
  }
  file { ['/etc/zulip/zulip.conf', '/etc/zulip/settings.py']:
    ensure  => 'file',
    require => File['/etc/zulip'],
    mode    => '0644',
    owner   => 'zulip',
    group   => 'zulip',
  }
  file { '/etc/zulip/zulip-secrets.conf':
    ensure  => 'file',
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
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
    mode   => '0640',
  }

  file { '/var/log/zulip/queue_error':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
    mode   => '0640',
  }

  file { '/var/log/zulip/queue_stats':
    ensure => 'directory',
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
