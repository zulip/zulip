class zulip::app_frontend {
  class { 'zulip::base': }
  class { 'zulip::rabbit': }
  class { 'zulip::nginx': }
  class { 'zulip::supervisor': }

  $web_packages = [ "memcached", "python-pylibmc", "python-tornado", "python-django",
                    "python-pygments", "python-flup", "python-psycopg2",
                    "yui-compressor", "python-django-auth-openid",
                    "python-django-statsd-mozilla", "python-dns",
                    "build-essential", "libssl-dev", "python-ujson",
                    "python-defusedxml", "python-twitter",
                    "python-twisted", "python-markdown",
                    "python-django-south", "python-mock", "python-pika",
                    "python-django-pipeline", "hunspell-en-us",
                    "python-django-bitfield", "python-embedly",
                    "python-postmonkey", "python-django-jstemplate",
                    "redis-server", "python-redis", "python-django-guardian",
                    "python-diff-match-patch", "python-sourcemap",]
  package { $web_packages: ensure => "installed" }

  file { "/etc/nginx/humbug-include/":
    require => Package[nginx],
    recurse => true,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/zulip/nginx/humbug-include/",
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
  file { "/etc/supervisor/conf.d/humbug.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/zulip/supervisord/conf.d/humbug.conf",
    notify => Service["supervisor"],
  }
  file { "/home/humbug/tornado":
    ensure => directory,
    owner => "humbug",
    group => "humbug",
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
}
