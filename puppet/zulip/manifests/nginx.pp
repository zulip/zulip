class zulip::nginx {
  include zulip::common
  $web_packages = [
    # Needed to run nginx with the modules we use
    $zulip::common::nginx,
  ]
  package { $web_packages: ensure => 'installed' }

  if $::osfamily == 'redhat' {
    file { '/etc/nginx/sites-available':
      ensure => 'directory',
      owner  => 'root',
      group  => 'root',
    }
    file { '/etc/nginx/sites-enabled':
      ensure => 'directory',
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

  # Nginx versions 1.4.6 and older do not support quoted URLs with the
  # X-Accel-Redirect / "sendfile" feature, which are required for
  # unicode support in filenames.  As a result, we use the fancier
  # django-sendfile behavior only when a sufficiently current version
  # of nginx is present (e.g.. Xenial).  Older versions (e.g. Trusty)
  # retain the older, less secure, file upload behavior; we expect
  # that this will stop being relevant when we drop Trusty support
  # from Zulip altogether, no later than when Trusty reaches EOL in 2019.
  $uploads_route = $zulip::base::release_name ? {
    'trusty' => 'puppet:///modules/zulip/nginx/zulip-include-maybe/uploads-route.direct',
    default  => 'puppet:///modules/zulip/nginx/zulip-include-maybe/uploads-route.internal',
  }
  $no_serve_uploads = zulipconf('application_server', 'no_serve_uploads', '')
  if $no_serve_uploads != '' {
    # If we're not serving uploads locally, set the appropriate API headers for it.
    $uploads_route = 'puppet:///modules/zulip/nginx/zulip-include-maybe/uploads-route.noserve'
  }

  file { '/etc/nginx/zulip-include/uploads.route':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    source  => $uploads_route,
  }

  file { '/etc/nginx/nginx.conf':
    ensure  => file,
    require => Package[$zulip::common::nginx],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    notify  => Service['nginx'],
    source  => 'puppet:///modules/zulip/nginx/nginx.conf',
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
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'adm',
    mode   => '0650'
  }

  file { ['/var/lib/zulip', '/var/lib/zulip/certbot-webroot']:
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'adm',
    mode   => '0660',
  }

  service { 'nginx':
    ensure     => running,
  }
}
