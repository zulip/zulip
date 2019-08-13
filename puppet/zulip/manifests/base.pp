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
        # Used in scripts
        'netcat',
        # Nagios plugins; needed to ensure $zulip::common::nagios_plugins exists
        'nagios-plugins-basic',
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
        'cronie'
      ]
    }
    default: {
      fail('osfamily not supported')
    }
  }
  package { $base_packages: ensure => 'installed' }

  $postgres_version = $release_name ? {
    'wheezy'  => '9.1',
    'jessie'  => '9.4',
    'stretch' => '9.6',
    'buster'  => '11',
    'precise' => '9.1',
    'trusty'  => '9.3',
    'vivid'   => '9.4',
    'wily'    => '9.4',
    'xenial'  => '9.5',
    'bionic'  => '10',
    'CentOS7' => '10',
  }

  $normal_queues = [
    'deferred_work',
    'digest_emails',
    'email_mirror',
    'embed_links',
    'embedded_bots',
    'error_reports',
    'feedback_messages',
    'invites',
    'missedmessage_email_senders',
    'email_senders',
    'missedmessage_emails',
    'missedmessage_mobile_notifications',
    'outgoing_webhooks',
    'signups',
    'slow_queries',
    'user_activity',
    'user_activity_interval',
    'user_presence',
  ]

  # $::memorysize_mb is a string in Facter < 3.0 and a double in Facter ≥ 3.0.
  # Either way, convert it to an integer.
  $total_memory_mb_array = scanf("${::memorysize_mb} ", '%i')
  $total_memory_mb = $total_memory_mb_array[0]

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
