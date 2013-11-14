class zulip_internal::prod_app_frontend {
  include zulip_internal::base
  include zulip_internal::app_frontend

  file { "/etc/nginx/sites-available/zulip":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip_internal/nginx/sites-available/zulip",
  }
  file { '/etc/nginx/sites-enabled/zulip':
    ensure => 'link',
    target => '/etc/nginx/sites-available/zulip',
  }

  file { [ "/srv/www/", "/srv/www/dist/", "/srv/www/dist/api",
           "/srv/www/dist/apps/", "/srv/www/dist/apps/mac/",
           "/srv/www/dist/apps/win/", "/srv/www/enterprise/",
           "/srv/www/enterprise/download/" ]:
    ensure => "directory",
    owner      => "zulip",
    group      => "zulip",
    mode       => 644,
  }

  file { "/srv/www/dist/apps/mac/sparkle.xml":
    ensure => file,
    require    => File['/srv/www/dist/apps/mac/'],
    owner  => "zulip",
    group  => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_internal/sparkle/mac/sparkle.xml",
  }
  file { "/srv/www/dist/apps/mac/sparkle-changelog.html":
    ensure => file,
    require    => File['/srv/www/dist/apps/mac/'],
    owner  => "zulip",
    group  => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_internal/sparkle/mac/sparkle-changelog.html",
  }
  file { "/srv/www/dist/apps/win/sparkle.xml":
    ensure => file,
    require    => File['/srv/www/dist/apps/win/'],
    owner  => "zulip",
    group  => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_internal/sparkle/win/sparkle.xml",
  }
  file { "/srv/www/dist/apps/win/sparkle-changelog.html":
    ensure => file,
    require    => File['/srv/www/dist/apps/win/'],
    owner  => "zulip",
    group  => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_internal/sparkle/win/sparkle-changelog.html",
  }

  file { "/srv/www/dist/apps/sso/mac/sparkle.xml":
    ensure => file,
    require    => File['/srv/www/dist/apps/sso/mac/'],
    owner  => "zulip",
    group  => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_internal/sparkle/sso/mac/sparkle.xml",
  }
  file { "/srv/www/dist/apps/sso/mac/sparkle-changelog.html":
    ensure => file,
    require    => File['/srv/www/dist/apps/sso/mac/'],
    owner  => "zulip",
    group  => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_internal/sparkle/sso/mac/sparkle-changelog.html",
  }
  file { "/srv/www/dist/apps/sso/win/sparkle.xml":
    ensure => file,
    require    => File['/srv/www/dist/apps/sso/win/'],
    owner  => "zulip",
    group  => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_internal/sparkle/sso/win/sparkle.xml",
  }
  file { "/srv/www/dist/apps/sso/win/sparkle-changelog.html":
    ensure => file,
    require    => File['/srv/www/dist/apps/sso/win/'],
    owner  => "zulip",
    group  => "zulip",
    mode => 644,
    source => "puppet:///modules/zulip_internal/sparkle/sso/win/sparkle-changelog.html",
  }
  # Prod has our Apple Push Notifications Service private key at
  # /etc/ssl/django-private/apns-dist.pem
}
