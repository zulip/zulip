class zulip::app_frontend {
  include zulip::rabbit
  include zulip::nginx
  include zulip::supervisor

  $web_packages = [ # Needed for memcached usage
                    "memcached",
                    "python-pylibmc",
                    # Fast JSON parser
                    "python-ujson",
                    # Django dependencies
                    "python-django",
                    "python-django-jstemplate",
                    "python-django-guardian",
                    "python-django-auth-openid",
                    "python-django-south",
                    "python-django-pipeline",
                    "python-django-bitfield",
                    # Tornado dependencies
                    "python-tornado",
                    "python-sockjs-tornado",
                    # Needed for our fastcgi setup
                    "python-flup",
                    # Needed for markdown processing
                    "python-markdown",
                    "python-pygments",
                    # Used for Hesiod lookups, etc.
                    "python-dns",
                    # Needed to access our database
                    "postgresql-client-9.1",
                    "python-psycopg2",
                    # Needed for integrations
                    "python-twitter",
                    "python-embedly",
                    "python-defusedxml",
                    # Needed for the email mirror
                    "python-twisted",
                    "python-html2text",
                    # Needed to access rabbitmq
                    "python-pika",
                    # Needed for timezone work
                    "python-tz",
                    # Needed to parse source maps for error reporting
                    "python-sourcemap",
                    # Needed for redis
                    "redis-server",
                    "python-redis",
                    # Needed for S3 file uploads
                    "python-boto",
                    # Needed to send email
                    "python-postmonkey",
                    "python-mandrill",
                    # Needed to generate diffs for edits
                    "python-diff-match-patch",
                    # Needed for iOS
                    "python-apns-client",
                    # Needed for avatar image resizing
                    "python-imaging",
                    ]
  define safepackage ( $ensure = present ) {
    if !defined(Package[$title]) {
      package { $title: ensure => $ensure }
    }
  }
  safepackage { $web_packages: ensure => "installed" }

  file { "/etc/nginx/zulip-include/":
    require => Package[nginx],
    recurse => true,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/zulip-include/",
    notify => Service["nginx"],
  }
  file { "/etc/memcached.conf":
    require => Package[memcached],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/memcached.conf",
  }
  file { "/etc/supervisor/conf.d/zulip.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/supervisor/conf.d/zulip.conf",
    notify => Service["supervisor"],
  }
  file { "/home/zulip/tornado":
    ensure => directory,
    owner => "zulip",
    group => "zulip",
    mode => 755,
  }
  file { "/etc/redis/redis.conf":
    require => Package[redis-server],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/redis/redis.conf",
  }
  service { 'redis-server':
    ensure     => running,
    subscribe  => File['/etc/redis/redis.conf'],
  }
  service { 'memcached':
    ensure     => running,
    subscribe  => File['/etc/memcached.conf'],
  }
  file { '/home/zulip/logs':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }
  file { '/home/zulip/deployments':
    ensure => 'directory',
    owner  => 'zulip',
    group  => 'zulip',
  }
}
