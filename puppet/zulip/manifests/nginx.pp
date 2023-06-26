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
  $worker_connections = zulipconf('application_server', 'nginx_worker_connections', 10000)
  file { '/etc/nginx/nginx.conf':
    ensure  => file,
    require => Package[$zulip::common::nginx, 'ca-certificates'],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    content => template('zulip/nginx.conf.template.erb'),
  }

  $loadbalancers = split(zulipconf('loadbalancer', 'ips', ''), ',')
  file { '/etc/nginx/zulip-include/trusted-proto':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    content => template('zulip/nginx/trusted-proto.template.erb'),
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
    mode   => '0750',
  }
  $access_log_retention_days = zulipconf('application_server','access_log_retention_days', 14)
  file { '/etc/logrotate.d/nginx':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/logrotate/nginx.template.erb'),
  }
  package { 'certbot':
    ensure => installed,
  }
  file { ['/var/lib/zulip', '/var/lib/zulip/certbot-webroot']:
    ensure => directory,
    owner  => 'zulip',
    group  => 'adm',
    mode   => '0770',
  }

  service { 'nginx':
    ensure     => running,
  }
}
