class zulip::memcached {
  include zulip::sasl_modules

  $memcached_packages = $::osfamily ? {
    'debian' => [ 'memcached', 'sasl2-bin' ],
    'redhat' => [ 'memcached' ],
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
  exec { 'generate_memcached_sasldb2':
    creates => '/etc/sasl2/memcached-sasldb2',
    require => [
      Package[$memcached_packages],
      Package[$zulip::sasl_modules::sasl_module_packages],
      File['/etc/sasl2/memcached-zulip-password'],
    ],
    # Pass the hostname explicitly because otherwise saslpasswd2
    # lowercases it and memcached does not.
    command => "bash -c 'saslpasswd2 -p -f /etc/sasl2/memcached-sasldb2 \
-a memcached -u \"\$HOSTNAME\" zulip < /etc/sasl2/memcached-zulip-password'",
  }
  file { '/etc/sasl2/memcached-sasldb2':
    require => Exec[generate_memcached_sasldb2],
    owner   => 'memcache',
    group   => 'memcache',
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
  }
}
