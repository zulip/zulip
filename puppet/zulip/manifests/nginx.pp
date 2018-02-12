class zulip::nginx {
  $web_packages = [# Needed to run nginx with the modules we use
                   "nginx-full",
                   ]
  package { $web_packages: ensure => "installed" }

  file { "/etc/nginx/zulip-include/":
    require => Package["nginx-full"],
    recurse => true,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/zulip-include-common/",
    notify => Service["nginx"],
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

  file { "/etc/nginx/zulip-include/uploads.route":
    require => Package["nginx-full"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    notify => Service["nginx"],
    source => $uploads_route,
  }

  file { "/etc/nginx/nginx.conf":
    require => Package["nginx-full"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    notify => Service["nginx"],
    source => "puppet:///modules/zulip/nginx/nginx.conf",
  }

  file { "/etc/nginx/uwsgi_params":
    require => Package["nginx-full"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    notify => Service["nginx"],
    source => "puppet:///modules/zulip/nginx/uwsgi_params",
  }

  file { "/etc/nginx/sites-enabled/default":
    notify => Service["nginx"],
    ensure => absent,
  }

  file { '/var/log/nginx':
    ensure     => "directory",
    owner      => "zulip",
    group      => "adm",
    mode       => 650
  }

  file { ["/var/lib/zulip", "/var/lib/zulip/certbot-webroot"]:
    ensure     => "directory",
    owner      => "zulip",
    group      => "adm",
    mode       => 660,
  }

  service { 'nginx':
    ensure     => running,
  }
}
