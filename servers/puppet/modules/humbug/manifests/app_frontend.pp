class humbug::app_frontend {
  class { 'humbug::base': }
  class { 'humbug::rabbit': }

  $web_packages = [ "nginx", "memcached", "python-pylibmc", "python-tornado", "python-django",
                    "python-pygments", "python-flup", "ipython", "python-psycopg2",
                    "yui-compressor", "python-django-auth-openid",
                    "build-essential", "libssl-dev", ]
  package { $web_packages: ensure => "installed" }

  # This next block can go away once we upgrade to Wheezy, which won't
  # have Python 2.5 at all.
  $web_nopackages = [ "python2.5", "python2.5-minimal" ]
  package { $web_nopackages: ensure => "absent" }

  file { "/etc/nginx/nginx.conf":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/nginx/nginx.conf",
  }
  file { "/etc/nginx/humbug-include/":
    require => Package[nginx],
    recurse => true,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/nginx/humbug-include/",
  }
  file { "/etc/nginx/sites-available/humbug":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/nginx/sites-available/humbug",
  }
  file { "/etc/memcached.conf":
    require => Package[memcached],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "puppet:///modules/humbug/memcached.conf",
  }
  # TODO: I think we need to restart memcached after deploying this

  exec {"pip-django-pipeline":
    command  => "/usr/bin/pip install django-pipeline",
    creates  => "/usr/local/lib/python2.6/dist-packages/pipeline",
    require  => Package['python-pip'],
  }

  # TODO: Add /usr/lib/nagios/plugins/check_send_receive_time ->
  # /home/humbug/humbug/api/humbug/bots/check_send_receive.py symlink

  # TODO: Setup the API distribution directory at /srv/www/dist/api/.

  # TODO: Ensure Django 1.5 is installed; this should be possible via
  # the backports-sloppy mechanism or via backports once we upgrade to
  # wheezy.
}
