# Default configuration for a Zulip app frontend
class zulip::app_frontend {
  include zulip::common
  include zulip::app_frontend_base
  include zulip::app_frontend_once

  $nginx_http_only = zulipconf('application_server', 'http_only', undef)
  $no_serve_uploads = zulipconf('application_server', 'no_serve_uploads', undef)
  $ssl_dir = $::osfamily ? {
    'debian' => '/etc/ssl',
    'redhat' => '/etc/pki/tls',
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
  file { '/etc/logrotate.d/zulip':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/logrotate/zulip',
  }
  file { '/etc/nginx/sites-enabled/zulip-enterprise':
    ensure  => 'link',
    require => Package[$zulip::common::nginx],
    target  => '/etc/nginx/sites-available/zulip-enterprise',
    notify  => Service['nginx'],
  }

  # Trigger 2x a day certbot renew
  file { '/etc/cron.d/certbot-renew':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/certbot-renew',
  }

  # Restart the server regularly to avoid potential memory leak problems.
  file { '/etc/cron.d/restart-zulip':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/cron.d/restart-zulip',
  }
}
