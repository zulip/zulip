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
  $packages = [ "screen", "sudo", "strace", "vim", "emacs", "git", "python-tz", "sqlite3", "python-tornado",  "python-simplejson", "python-pygments", "ipython", "python-django", "openssh-server", "python-pip", "puppet-el", ]
  package { $packages: ensure => "installed" }

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
    source     => '/root/humbug/servers/puppet/files/authorized_keys',
  }

  file { '/home/humbug/.ssh':
    ensure     => directory,
    require    => User['humbug'],
    mode       => 600,
  }

  file { '/root/.ssh/authorized_keys':
    ensure     => file,
    mode       => 600,
    source     => '/root/humbug/servers/puppet/files/root_authorized_keys',
  }

  file { '/etc/puppet/puppet.conf':
    ensure     => file,
    mode       => 640,
    source     => '/root/humbug/servers/puppet/puppet.conf',
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

  common::line { '/etc/sudoers':
    require    => Package['sudo'],
    file       => '/etc/sudoers',
    line       => 'humbug    ALL=(ALL) NOPASSWD: ALL',
  }
}

class humbug_web_base {
  $web_packages = [ "apache2", "gitit", ]
  package { $web_packages: ensure => "installed" }

  apache2mod { [ "headers", "proxy", "proxy_http", "rewrite", "auth_digest", ]:
    ensure => present,
  }

  # Intentionally seperate in the hopes that this fixes dumb dependency problems
  apache2mod { "ssl":
    ensure => present,
  }

  # FIXME: Stop using pip since it is insecure
  exec {"pip":
    command  => "pip install django-jstemplate",
    onlyif   => "test ! -d /usr/local/lib/python2.6/dist-packages/jstemplate"
  }
  exec {"pip2":
    command  => "pip install markdown",
    onlyif   => "test ! -d /usr/local/lib/python2.6/dist-packages/markdown"
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
    source => "/root/humbug/servers/puppet/files/apache/certs/humbug-self-signed.key",
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
  apache2site { 'app':
    require => [File['/etc/apache2/sites-available/'],
                Apache2mod['headers'], Apache2mod['ssl'],
                ],
    ensure => present,
  }
}

class humbug_wiki {
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

class { "humbug_base": }
class { "humbug_web_base": }
class { "humbug_wiki": }
class { "humbug_app_frontend": }
