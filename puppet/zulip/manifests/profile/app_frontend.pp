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

  # We used to install a cron job, but certbot now has a systemd cron
  # that does better.  This can be removed once upgrading from 5.0 is
  # no longer possible.
  file { '/etc/cron.d/certbot-renew':
    ensure => absent,
  }

  # Reload nginx after deploying a new cert.
  file { ['/etc/letsencrypt/renewal-hooks', '/etc/letsencrypt/renewal-hooks/deploy']:
    ensure  => directory,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    require => Package[certbot],
  }
  file { '/etc/letsencrypt/renewal-hooks/deploy/001-nginx.sh':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/letsencrypt/nginx-deploy-hook.sh',
    require => Package[certbot],
  }
  if ! $nginx_http_only {
    exec { 'fix-standalone-certbot':
      onlyif  => @(EOT),
        test -L /etc/ssl/certs/zulip.combined-chain.crt &&
        readlink /etc/ssl/certs/zulip.combined-chain.crt | grep -q /etc/letsencrypt/live/ &&
        test -d /etc/letsencrypt/renewal &&
        grep -qx "authenticator = standalone" /etc/letsencrypt/renewal/*.conf
        | EOT
      command => "${facts['zulip_scripts_path']}/lib/fix-standalone-certbot",
    }
  }

  # Restart the server regularly to avoid potential memory leak problems.
  zulip::cron { 'restart-zulip':
    hour    => '6',
    minute  => '0',
    dow     => '7',
    command => '/home/zulip/deployments/current/scripts/restart-server --fill-cache',
  }
}
