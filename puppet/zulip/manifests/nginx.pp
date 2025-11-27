class zulip::nginx {
  $web_packages = [
    # Needed to run nginx with the modules we use
    $zulip::common::nginx,
    'ca-certificates',
  ]
  package { $web_packages: ensure => installed }

  if $facts['os']['family'] == 'RedHat' {
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

  if $facts['os']['family'] == 'Debian' {
      $ca_crt = '/etc/ssl/certs/ca-certificates.crt'
  } else {
      $ca_crt = '/etc/pki/tls/certs/ca-bundle.crt'
  }

  $loadbalancers = split(zulipconf('loadbalancer', 'ips', ''), ',')
  $lb_rejects_http_requests = zulipconf('loadbalancer', 'rejects_http_requests', false)
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

  exec { 'add-zulip-to-adm-group':
    command => '/usr/sbin/usermod -a -G adm zulip',
    unless  => '/usr/bin/id zulip >/dev/null 2>&1 && /usr/bin/groups zulip 2>/dev/null | /bin/grep -q "\\badm\\b"',
  }
  $nginx_user = $facts['os']['family'] ? {
    'Debian' => 'www-data',
    'RedHat' => 'nginx',
    default  => 'www-data',
  }
  file { '/var/log/nginx':
    ensure => directory,
    owner  => $nginx_user,
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
    ensure => running,
  }
}
