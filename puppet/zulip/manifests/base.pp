class zulip::base {
  include apt
  $base_packages = [ # Accurate time is essential
                     "ntp",
                     # Used in scripts
                     "netcat",
                     # Nagios plugins; needed to ensure /var/lib/nagios_plugins exists
                     "nagios-plugins-basic",
                     # Used to read /etc/zulip/zulip.conf for `zulipconf` puppet function
                     "crudini",
                     # Used for tools like sponge
                     "moreutils",
                     ]
  package { $base_packages: ensure => "installed" }

  $release_name = $operatingsystemrelease ? {
    # Debian releases
    /7.[0-9]*/ => 'wheezy',
    /8.[0-9]*/ => 'jessie',
    # Ubuntu releases
    '12.04' => 'precise',
    '14.04' => 'trusty',
    '15.04' => 'vivid',
    '15.10' => 'wily',
    '16.04' => 'xenial',
  }

  $postgres_version = $release_name ? {
    'wheezy'  => '9.1',
    'jessie'  => '9.4',
    'precise' => '9.1',
    'trusty'  => '9.3',
    'vivid'   => '9.4',
    'wily'    => '9.4',
    'xenial'  => '9.5',
  }

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
    ensure     => 'directory',
    mode       => 644,
    owner      => 'zulip',
    group      => 'zulip',
  }

  file { '/etc/security/limits.conf':
    ensure     => file,
    mode       => 640,
    owner      => "root",
    group      => "root",
    source     => 'puppet:///modules/zulip/limits.conf',
  }

  # This directory is written to by cron jobs for reading by Nagios
  file { '/var/lib/nagios_state/':
    ensure     => directory,
    group      => 'zulip',
    mode       => 774,
  }

  file { '/var/log/zulip':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
    mode   => 640,
  }

  file { '/var/log/zulip/queue_error':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
    mode   => 640,
  }

  file { "/usr/lib/nagios/plugins/zulip_base":
    require => Package[nagios-plugins-basic],
    recurse => true,
    purge => true,
    owner => "root",
    group => "root",
    mode => 755,
    source => "puppet:///modules/zulip/nagios_plugins/zulip_base",
  }
}
