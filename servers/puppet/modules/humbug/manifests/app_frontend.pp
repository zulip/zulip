class humbug::app_frontend {
  class { 'humbug::base': }
  class { 'humbug::rabbit': }
  class { 'humbug::nginx': }
  class { 'humbug::supervisor': }

  $web_packages = [ "memcached", "python-pylibmc", "python-tornado", "python-django",
                    "python-pygments", "python-flup", "ipython", "python-psycopg2",
                    "yui-compressor", "python-django-auth-openid",
                    "python-django-statsd-mozilla",
                    "build-essential", "libssl-dev",
                    "python-boto", "python-defusedxml", "python-twitter",
                    "python-twisted", "python-markdown",
                    "python-django-south", "python-mock", "python-pika",
                    "python-django-pipeline", "hunspell-en-us",
                    "python-django-bitfield", "python-embedly",
                    "python-postmonkey", "python-django-jstemplate",
                    "redis-server", "python-redis",
                    "python-diff-match-patch",]
  package { $web_packages: ensure => "installed" }

  file { "/etc/nginx/humbug-include/":
    require => Package[nginx],
    recurse => true,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/nginx/humbug-include/",
    notify => Service["nginx"],
  }
  file { "/etc/memcached.conf":
    require => Package[memcached],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/memcached.conf",
  }
  file { "/etc/supervisor/conf.d/humbug.conf":
    require => Package[supervisor],
    ensure => file,
    owner => "root",
    group => "root",
    mode => 644,
    source => "puppet:///modules/humbug/supervisord/conf.d/humbug.conf",
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
    source => "puppet:///modules/humbug/redis/redis.conf",
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
