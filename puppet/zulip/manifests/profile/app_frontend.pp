# Default configuration for a Zulip app frontend
class zulip::profile::app_frontend {
  include zulip::profile::base
  include zulip::app_frontend_base
  include zulip::app_frontend_once

  $nginx_http_only = zulipconf('application_server', 'http_only', false)
  if $nginx_http_only {
    $nginx_listen_port = zulipconf('application_server', 'nginx_listen_port', 80)
  } else {
    $nginx_listen_port = zulipconf('application_server', 'nginx_listen_port', 443)
  }
  $ssl_dir = $facts['os']['family'] ? {
    'Debian' => '/etc/ssl',
    'RedHat' => '/etc/pki/tls',
  }
  file { '/etc/nginx/sites-available/zulip-enterprise':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/nginx/zulip-enterprise.template.erb'),
    notify  => Service['nginx'],
  }
  file { '/etc/nginx/sites-enabled/zulip-enterprise':
    ensure  => link,
    require => Package[$zulip::common::nginx],
    target  => '/etc/nginx/sites-available/zulip-enterprise',
    notify  => Service['nginx'],
  }

  # Reload nginx after deploying a new cert.
  file { '/etc/letsencrypt/renewal-hooks/deploy/001-nginx.sh':
    # This was renumbered
    ensure => absent,
  }
  file { '/etc/letsencrypt/renewal-hooks/deploy/020-symlink.sh':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/letsencrypt/020-symlink.sh',
    require => [
      Package[certbot],
      File['/etc/letsencrypt/renewal-hooks/deploy'],
    ]
  }
  file { '/etc/letsencrypt/renewal-hooks/deploy/050-nginx.sh':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0755',
    source => 'puppet:///modules/zulip/letsencrypt/050-nginx.sh',
  }

  # Restart the server regularly to avoid potential memory leak problems.
  zulip::cron { 'restart-zulip':
    hour    => '6',
    minute  => '0',
    dow     => '0',
    command => '/home/zulip/deployments/current/scripts/restart-server --fill-cache --skip-client-reloads',
  }
}
