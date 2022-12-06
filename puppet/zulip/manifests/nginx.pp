class zulip::nginx {
  $web_packages = [
    # Needed to run nginx with the modules we use
    $zulip::common::nginx,
    'ca-certificates',
  ]
  package { $web_packages: ensure => installed }

  if $::os['family'] == 'RedHat' {
    file { '/etc/nginx/sites-available':
      ensure => directory,
      owner  => 'root',
      group  => 'root',
    }
    file { '/etc/nginx/sites-enabled':
      ensure => directory,
      owner  => 'root',
      group  => 'root',
    }
  }

  file { '/etc/nginx/zulip-include/':
    require => Package[$zulip::common::nginx],
    recurse => true,
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/nginx/zulip-include-common/',
    notify  => Service['nginx'],
  }

  file { '/etc/nginx/dhparam.pem':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    source  => 'puppet:///modules/zulip/nginx/dhparam.pem',
  }

  if $::os['family'] == 'Debian' {
      $ca_crt = '/etc/ssl/certs/ca-certificates.crt'
  } else {
      $ca_crt = '/etc/pki/tls/certs/ca-bundle.crt'
  }
  file { '/etc/nginx/nginx.conf':
    ensure  => file,
    require => Package[$zulip::common::nginx, 'ca-certificates'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    content => template('zulip/nginx.conf.template.erb'),
  }

  file { '/etc/nginx/uwsgi_params':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    source  => 'puppet:///modules/zulip/nginx/uwsgi_params',
  }

  file { '/etc/nginx/sites-enabled/default':
    ensure => absent,
    notify => Service['nginx'],
  }

  file { '/var/log/nginx':
    ensure => directory,
    owner  => 'zulip',
    group  => 'adm',
    mode   => '0650',
  }
  file { '/etc/logrotate.d/nginx':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    source  => 'puppet:///modules/zulip/logrotate/nginx',
  }
  package { 'certbot':
    ensure => installed,
  }
  file { ['/var/lib/zulip', '/var/lib/zulip/certbot-webroot']:
    ensure => directory,
    owner  => 'zulip',
    group  => 'adm',
    mode   => '0660',
  }

  service { 'nginx':
    ensure     => running,
  }
}
