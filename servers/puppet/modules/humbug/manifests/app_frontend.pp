class humbug::app_frontend {
  class { 'humbug::base': }
  class { 'humbug::rabbit': }

  $web_packages = [ "nginx", "memcached", "python-pylibmc", "python-tornado", "python-django",
                    "python-pygments", "python-flup", "ipython", "python-psycopg2",
                    "yui-compressor", "python-django-auth-openid",
		    "python-django-statsd-mozilla",
                    "build-essential", "libssl-dev", "supervisor",
		    "python-boto", "python-defusedxml", "python-twitter",
		    "python-twisted", "python-markdown", "python-requests",
		    "python-django-south", "python-mock", "python-pika",
		    "python-django-pipeline", "hunspell-en-us",
		    "python-django-bitfield", "python-embedly",
		    "python-postmonkey", "python-django-jstemplate"]
  package { $web_packages: ensure => "installed" }

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


  file { '/etc/nginx/sites-enabled/humbug':
    ensure => 'link',
    target => '/etc/nginx/sites-available/humbug',
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
  }
  file { "/var/log/humbug":
    ensure => directory,
    owner => "root",
    group => "root",
    mode => 755,
  }
  file { "/home/humbug/tornado":
    ensure => directory,
    owner => "humbug",
    group => "humbug",
    mode => 755,
  }

  # TODO: I think we need to restart memcached after deploying this

  exec {"pip-django-pipeline":
    command  => "/usr/bin/pip install django-pipeline",
    creates  => "/usr/local/lib/python2.6/dist-packages/pipeline",
    require  => Package['python-pip'],
  }
  exec {"humbug-server":
    command => "/etc/init.d/supervisor restart",
    require => [File["/etc/supervisor/conf.d/humbug.conf"],
                File["/var/log/humbug"],
                Exec["pip-django-pipeline"],]
  }

  # TODO: Add /usr/lib/nagios/plugins/check_send_receive_time ->
  # /home/humbug/humbug-deployments/current/api/humbug/bots/check_send_receive.py symlink

  # TODO: Setup the API distribution directory at /srv/www/dist/api/.

  # TODO: Ensure Django 1.5 is installed; this should be possible via
  # the backports-sloppy mechanism or via backports once we upgrade to
  # wheezy.
}
