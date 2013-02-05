# Puppet config for humbug-dev

# globals
Exec { path => "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" }

# modules
import "apache.rb"
import "/root/humbug/servers/puppet/modules/apt/manifests/*.pp"
import "/root/humbug/servers/puppet/modules/common/manifests/*.pp"

class {'apt': }
class {'apt::backports':
  priority => 600
}

## START LIBRARY FUNCTIONS

# Usage: Variant on common:append_if_no_such_line that initializes the
# File object for you.
define common::append ($file, $line) {
  file { $file:
    ensure => file,
  }
  exec { "/bin/echo '$line' >> '$file'":
    unless => "/bin/grep -Fxqe '$line' '$file'",
    path => "/bin",
    subscribe => File[$file],
  }
}

class humbug_base {
  $packages = [ "screen", "strace", "vim", "emacs23-nox", "git", "python-tz",
                "sqlite3", "ntp", "python-simplejson", "host",
                "openssh-server", "python-pip", "puppet-el",
                "iptables-persistent", "nagios-plugins-basic", "munin-node",
                "munin-plugins-extra" ]
  package { $packages: ensure => "installed" }

  # FIXME: Stop using pip since it is insecure
  exec {"pip":
    command  => "pip install django-jstemplate",
    onlyif   => "test ! -d /usr/local/lib/python2.6/dist-packages/jstemplate"
  }
  exec {"pip2":
    command  => "pip install markdown",
    onlyif   => "test ! -d /usr/local/lib/python2.6/dist-packages/markdown"
  }
  exec {"pip3":
    command  => "pip install requests",
    onlyif   => "test ! -d /usr/local/lib/python2.6/dist-packages/requests"
  }
  exec {"pip4":
    command  => "pip install pika",
    onlyif   => "test ! -d /usr/local/lib/python2.6/dist-packages/pika"
  }
  exec {"pip5":
    command  => "pip install South",
    onlyif   => "test ! -d /usr/local/lib/python2.6/dist-packages/south"
  }

  group { 'humbug':
    ensure     => present,
    gid        => '1000',
  }

  user { 'humbug':
    ensure     => present,
    uid        => '1000',
    gid        => '1000',
    require    => Group['humbug'],
    shell      => '/bin/bash',
    home       => '/home/humbug',
    managehome => true,
  }

  file { '/home/humbug/.ssh/authorized_keys':
    ensure     => file,
    require    => File['/home/humbug/.ssh'],
    mode       => 600,
    owner      => "humbug",
    group      => "humbug",
    source     => '/root/humbug/servers/puppet/files/authorized_keys',
  }

  file { '/home/humbug/.ssh':
    ensure     => directory,
    require    => User['humbug'],
    owner      => "humbug",
    group      => "humbug",
    mode       => 600,
  }

  file { '/root/.ssh/authorized_keys':
    ensure     => file,
    mode       => 600,
    source     => '/root/humbug/servers/puppet/files/root_authorized_keys',
  }

  # This is just an empty file.  It's used by the app to test if it's running
  # in production.
  file { '/etc/humbug-server':
    ensure     => file,
    mode       => 644,
    source     => '/root/humbug/servers/puppet/files/humbug-server',
  }

  file { '/etc/puppet/puppet.conf':
    ensure     => file,
    mode       => 640,
    source     => '/root/humbug/servers/puppet/puppet.conf',
  }

  file { '/etc/iptables/rules':
    ensure     => file,
    mode       => 600,
    source     => '/root/humbug/servers/puppet/files/iptables/rules',
  }

  file { '/etc/apt/apt.conf.d/02periodic':
    ensure     => file,
    mode       => 644,
    source     => '/root/humbug/servers/puppet/files/apt/apt.conf.d/02periodic',
  }

  common::append { '/etc/ssh/sshd_config':
    require    => Package['openssh-server'],
    file       => '/etc/ssh/sshd_config',
    line       => 'PasswordAuthentication no',
  }

  service { 'ssh':
    ensure     => running,
    subscribe  => File['/etc/ssh/sshd_config'],
  }
}

class humbug_apache_base {
  $apache_packages = [ "apache2", "libapache2-mod-wsgi", ]
  package { $apache_packages: ensure => "installed" }

  apache2mod { [ "headers", "proxy", "proxy_http", "rewrite", "auth_digest", "ssl" ]:
    ensure => present,
  }

  file { "/etc/apache2/users/":
    ensure   => directory,
    owner    => "www-data",
    group    => "www-data",
    mode     => 600,
  }

  file { "/etc/apache2/users/wiki":
    require => File["/etc/apache2/users/"],
    ensure => file,
    owner  => "www-data",
    group  => "www-data",
    mode => 600,
    source => "/root/humbug/servers/puppet/files/apache/users",
  }

  file { "/etc/apache2/certs/":
    ensure => directory,
    owner => "root",
    group => "root",
    mode => 644,
  }

  file { "/etc/apache2/certs/humbug-self-signed.crt":
    require => File["/etc/apache2/certs/"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 640,
    source => "/root/humbug/certs/humbug-self-signed.crt",
  }

  file { "/etc/apache2/certs/humbug-self-signed.key":
    require => File["/etc/apache2/certs/"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 600,
    source => "/root/humbug/certs/humbug-self-signed.key",
  }

  file { "/etc/apache2/ports.conf":
    require => Package[apache2],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 640,
    source => "/root/humbug/servers/puppet/files/apache/ports.conf",
  }

  file { "/etc/apache2/sites-available/":
    recurse => true,
    require => Package[apache2],
    owner  => "root",
    group  => "root",
    mode => 640,
    source => "/root/humbug/servers/puppet/files/apache/sites/",
  }

  apache2site { 'humbug-default':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }
}

class humbug_app_frontend {
  $web_packages = [ "nginx", "memcached", "python-pylibmc", "python-tornado", "python-django",
                    "python-pygments", "python-flup", "ipython", "python-psycopg2",
                    "yui-compressor", ]
  package { $web_packages: ensure => "installed" }
  file { "/etc/nginx/nginx.conf":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "/root/humbug/servers/puppet/files/nginx/nginx.conf",
  }
  file { "/etc/nginx/humbug-include/":
    require => Package[nginx],
    recurse => true,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "/root/humbug/servers/puppet/files/nginx/humbug-include/",
  }
  file { "/etc/nginx/sites-available/humbug":
    require => Package[nginx],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "/root/humbug/servers/puppet/files/nginx/sites-available/humbug",
  }

  exec {"pip6":
    command  => "pip install django-pipeline",
    onlyif   => "test ! -d /usr/local/lib/python2.6/dist-packages/django-pipeline"
  }

  # TODO: Add /usr/lib/nagios/plugins/check_send_receive_time ->
  # /home/humbug/humbug/api/humbug/bots/check_send_receive.py symlink
}

# TODO: Setup dotdeb repository for this, including apt preferences to
# only get the database from dotdeb.
class humbug_database {
  $db_packages = [ "mysql-server-5.5", ]
  package { $db_packages: ensure => "installed" }
  file { "/etc/mysql/my.cnf":
    require => Package["mysql-server-5.5"],
    ensure => file,
    owner  => "root",
    group  => "root",
    mode => 644,
    source => "/root/humbug/servers/puppet/files/mysql/my.cnf",
  }
}

class humbug_wiki {
  $wiki_packages = [ "gitit", ]
  package { $wiki_packages: ensure => "installed" }

  group { 'wiki':
    ensure     => present,
    gid        => '1100',
  }

  apache2site { 'wiki':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }

  user { 'wiki':
    ensure     => present,
    uid        => '1100',
    gid        => '1100',
    require    => Group['wiki'],
    shell      => '/bin/bash',
    home       => '/home/wiki',
    managehome => true,
  }

  file { "/home/wiki/wiki/":
    recurse => true,
    owner  => "wiki",
    group  => "wiki",
    source => "/root/humbug/servers/puppet/files/wiki",
  }
}

class humbug_trac {
  $trac_packages = [ "trac", ]
  package { $wiki_packages: ensure => "installed" }

  apache2site { 'trac':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }
  #TODO: Need to install our trac config
}

class humbug_nagios {
  $nagios_packages = [ "nagios3", "munin", "autossh" ]
  package { $nagios_packages: ensure => "installed" }

  apache2site { 'nagios':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }
  #TODO: Need to install our Nagios config
  #
  # Also need to run this sequence to enable commands to set the
  # permissions for using the Nagios commands feature
  #
  # /etc/init.d/nagios3 stop
  # dpkg-statoverride --update --add nagios www-data 2710 /var/lib/nagios3/rw
  # dpkg-statoverride --update --add nagios nagios 751 /var/lib/nagios3
  # /etc/init.d/nagios3 start
  #
  #
}

class humbug_zmirror {
  $zmirror_packages = [ "cython", "libzephyr-dev", "comerr-dev", "python-dev", "libzephyr4-krb5", "zephyr-clients",
                        "krb5-config", "krb5-user", "krb5-clients"]
  package { $zmirror_packages: ensure => "installed" }

  # TODO: Do the rest of our setup, which includes at least:
  # Configuring Kerberos and Zephyr for the MIT realm
  # Building python-zephyr after cloning it from https://github.com/ebroder/python-zephyr
  # Putting tabbott/extra's keytab on the system at /home/humbug/tabbott.extra.keytab
  # Setting api/bots/zephyr-mirror-crontab to be the Humbug user's crontab
  # Running the mirroring bot in a screen session with these arguments:
  # /home/humbug/api/bots/zephyr_mirror.py --root-path=/home/humbug/ --user=tabbott/extra --enable-log=/home/humbug/all_zephyrs_log --forward-class-messages
}

class humbug_postgres {
  $postgres_packages = [ "postgresql-9.1", "pgtune", ]
  package { $postgres_packages: ensure => "installed" }

  file { '/etc/sysctl.d/30-postgresql-shm.conf':
    ensure => file,
    owner  => root,
    group  => root,
    mode   => 644
  }

  file { "/etc/postgresql/9.1/main/postgresql.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 644,
    source => "/root/humbug/servers/puppet/files/postgresql/postgresql.conf",
  }

  file { "/etc/postgresql/9.1/main/pg_hba.conf":
    require => Package["postgresql-9.1"],
    ensure => file,
    owner  => "postgres",
    group  => "postgres",
    mode => 640,
    source => "/root/humbug/servers/puppet/files/postgresql/pg_hba.conf",
  }

  common::append_if_no_such_line { 'shmmax':
    require    => Package['postgresql-9.1'],
    file       => '/etc/sysctl.d/30-postgresql-shm.conf',
    line       => 'kernel.shmmax = 6979321856'
  }
  common::append_if_no_such_line { 'shmall':
    require    => Package['postgresql-9.1'],
    file       => '/etc/sysctl.d/30-postgresql-shm.conf',
    line       => 'kernel.shmall = 1703936'
  }

  exec { "sysctl_p":
    command  => "sysctl -p /etc/sysctl.d/30-postgresql-shm.conf",
    require  => [ Common::Append_if_no_such_line['shmmax'],
                  Common::Append_if_no_such_line['shmall'],
                ],
  }

  exec { "disable_logrotate":
    command => "dpkg-divert --rename --divert /etc/logrotate.d/postgresql-common.disabled --add /etc/logrotate.d/postgresql-common"
  }
}

class humbug_git {
  $git_packages = [ ]
  package { $git_packages: ensure => "installed" }

  # TODO: Should confirm git repos at /srv/git and then setup
  # /srv/git/humbug.git/hooks/post-receive ->
  # /home/humbug/humbug/tools/post-receive
}

class humbug_rabbit {
  $rabbit_packages = [ "rabbitmq-server" ]
  package { $rabbit_packages: ensure => "installed" }

  # TODO: Should also call exactly once "servers/configure-rabbitmq"
}

class humbug_bots {
  $bots_packages = [ "supervisor" ]
  package { $bots_packages: ensure => "installed" }

  file { '/var/log/humbug':
    ensure => 'directory',
    owner  => 'humbug',
    group  => 'humbug',
    mode   => 640,
  }

  file { '/etc/supervisor/conf.d/feedback-bot.conf':
    require => Package['supervisor'],
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => 640,
    source  => "/root/humbug/servers/puppet/files/supervisor/conf.d/feedback-bot.conf",
  }
}

class { "humbug_base": }
#class { "humbug_apache_base": }
#class { "humbug_wiki": }
#class { "humbug_app_frontend": }
#class { "humbug_database": }
#class { "humbug_postgres": }
#class { "humbug_zmirror": }
#class { "humbug_bots": }
#class { "humbug_rabbit": }
