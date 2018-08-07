class zulip::base {
  include apt
  $base_packages = [
    # Accurate time is essential
    'ntp',
    # Used in scripts including install-yarn.sh
    'curl',
    'wget',
    # Used in scripts
    'netcat',
    # Nagios plugins; needed to ensure /var/lib/nagios_plugins exists
    'nagios-plugins-basic',
    # Used to read /etc/zulip/zulip.conf for `zulipconf` puppet function
    'crudini',
    # Used for tools like sponge
    'moreutils',
    # Required for using HTTPS in apt repositories.
    'apt-transport-https',
    # Needed for the cron jobs installed by puppet
    'cron',
  ]
  package { $base_packages: ensure => 'installed' }

  $release_name = $::operatingsystemrelease ? {
    # Debian releases
    /^7.[0-9]*/ => 'wheezy',
    /^8.[0-9]*/ => 'jessie',
    /^9.[0-9]*/ => 'stretch',
    # Ubuntu releases
    '12.04' => 'precise',
    '14.04' => 'trusty',
    '15.04' => 'vivid',
    '15.10' => 'wily',
    '16.04' => 'xenial',
    '18.04' => 'bionic',
  }

  $postgres_version = $release_name ? {
    'wheezy'  => '9.1',
    'jessie'  => '9.4',
    'stretch' => '9.6',
    'precise' => '9.1',
    'trusty'  => '9.3',
    'vivid'   => '9.4',
    'wily'    => '9.4',
    'xenial'  => '9.5',
    'bionic'  => '10',
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

  # We can't use the built-in $memorysize fact because it's a string with human-readable units
  # Meanwhile $memorysize_mb is a string, and can't be compared with integers in puppet 4.
  $total_memory = regsubst(file('/proc/meminfo'), '^.*MemTotal:\s*(\d+) kB.*$', '\1', 'M') * 1024
  $total_memory_mb = $total_memory / 1024 / 1024

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
    ensure => 'file',
    require => File['/etc/zulip'],
    mode   => '0644',
    owner  => 'zulip',
    group  => 'zulip',
  }
  file { '/etc/zulip/zulip-secrets.conf':
    ensure => 'file',
    require => File['/etc/zulip'],
    mode   => '0640',
    owner  => 'zulip',
    group  => 'zulip',
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

  file { '/usr/lib/nagios/plugins/zulip_base':
    require => Package[nagios-plugins-basic],
    recurse => true,
    purge   => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/nagios_plugins/zulip_base',
  }
}
