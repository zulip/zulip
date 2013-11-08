class zulip::nginx {
  $web_packages = [# Needed to run nginx
                   "nginx",
                   ]
  package { $web_packages: ensure => "installed" }

  file { "/etc/nginx/nginx.conf":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    notify => Service["nginx"],
    source => "puppet:///modules/zulip/nginx/nginx.conf",
  }

  file { "/etc/nginx/fastcgi_params":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    notify => Service["nginx"],
    source => "puppet:///modules/zulip/nginx/fastcgi_params",
  }

  file { "/etc/nginx/sites-enabled/default":
    notify => Service["nginx"],
    ensure => absent,
  }

  service { 'nginx':
    ensure     => running,
  }
}

