class zulip::memcached {
  include zulip::sasl_modules
  include zulip::systemd_daemon_reload

  case $::osfamily {
    'debian': {
      $memcached_packages = [ 'memcached', 'sasl2-bin' ]
      $memcached_user = 'memcache'
    }
    'redhat': {
      $memcached_packages = [ 'memcached', 'cyrus-sasl' ]
      $memcached_user = 'memcached'
    }
    default: {
      fail('osfamily not supported')
    }
  }
  package { $memcached_packages: ensure => 'installed' }

  $memcached_memory = zulipconf('memcached', 'memory', $zulip::base::total_memory_mb / 8)
  file { '/etc/sasl2':
    ensure => directory,
  }
  file { '/etc/sasl2/memcached-zulip-password':
    # We cache the password in this file so we can check whether it
    # changed and avoid running saslpasswd2 if it didn't.
    require => File['/etc/sasl2'],
    owner   => 'root',
    group   => 'root',
    mode    => '0600',
    content => zulipsecret('secrets', 'memcached_password', ''),
    notify  => Exec[generate_memcached_sasldb2],
  }
  file { '/var/lib/zulip/memcached-sasldb2.stamp':
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => '1',
    notify  => Exec[generate_memcached_sasldb2],
  }
  exec { 'generate_memcached_sasldb2':
    require     => [
      Package[$memcached_packages],
      Package[$zulip::sasl_modules::sasl_module_packages],
    ],
    refreshonly => true,
    # Use localhost for the currently recommended MEMCACHED_USERNAME =
    # "zulip@localhost" and the hostname for compatibility with
    # MEMCACHED_USERNAME = "zulip".
    command     => "bash -euc '
rm -f /etc/sasl2/memcached-sasldb2
saslpasswd2 -p -f /etc/sasl2/memcached-sasldb2 \
    -a memcached -u localhost zulip < /etc/sasl2/memcached-zulip-password
saslpasswd2 -p -f /etc/sasl2/memcached-sasldb2 \
    -a memcached -u \"\$HOSTNAME\" zulip < /etc/sasl2/memcached-zulip-password
'",
  }
  file { '/etc/sasl2/memcached-sasldb2':
    require => Exec[generate_memcached_sasldb2],
    owner   => $memcached_user,
    group   => $memcached_user,
    mode    => '0600',
  }
  file { '/etc/sasl2/memcached.conf':
    require => File['/etc/sasl2'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/sasl2/memcached.conf',
    notify  => Service[memcached],
  }
  file { '/etc/systemd/system/memcached.service.d':
    ensure => directory,
  }
  file { '/etc/systemd/system/memcached.service.d/zulip-fix-sasl.conf':
    require => File['/etc/systemd/system/memcached.service.d'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => "\
# https://bugs.launchpad.net/ubuntu/+source/memcached/+bug/1878721
[Service]
Environment=SASL_CONF_PATH=/etc/sasl2
",
    notify  => [
      Class['zulip::systemd_daemon_reload'],
      Service['memcached'],
    ],
  }
  file { '/etc/memcached.conf':
    ensure  => file,
    require => [
      Package[$memcached_packages],
      Package[$zulip::sasl_modules::sasl_module_packages]
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/memcached.conf.template.erb'),
  }
  service { 'memcached':
    ensure    => running,
    subscribe => File['/etc/memcached.conf'],
    require   => Class['zulip::systemd_daemon_reload'];
  }
}
