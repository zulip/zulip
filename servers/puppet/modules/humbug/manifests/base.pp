class humbug::base {
  class {'humbug': }

  $packages = [ "screen", "strace", "vim", "emacs23-nox", "git", "python-tz",
                "sqlite3", "ntp", "python-simplejson", "host",
                "openssh-server", "python-pip", "puppet-el",
                "iptables-persistent", "nagios-plugins-basic", "munin-node",
                "munin-plugins-extra" ]
  package { $packages: ensure => "installed" }

  # FIXME: Stop using pip since it is insecure
  exec {"pip":
    command  => "/usr/bin/pip install django-jstemplate",
    creates  => "/usr/local/lib/python2.6/dist-packages/jstemplate"
  }
  exec {"pip2":
    command  => "/usr/bin/pip install markdown",
    creates  => "/usr/local/lib/python2.6/dist-packages/markdown"
  }
  exec {"pip3":
    command  => "/usr/bin/pip install requests",
    creates  => "/usr/local/lib/python2.6/dist-packages/requests"
  }
  exec {"pip4":
    command  => "/usr/bin/pip install pika",
    creates  => "/usr/local/lib/python2.6/dist-packages/pika"
  }
  exec {"pip5":
    command  => "/usr/bin/pip install South",
    creates  => "/usr/local/lib/python2.6/dist-packages/south"
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

  file { '/etc/ssh/sshd_config':
    require    => Package['openssh-server'],
    ensure     => file,
  }

  # TODO: we should really just have a known sshd_config file
  common::line { 'no_password_auth':
    file       => '/etc/ssh/sshd_config',
    line       => 'PasswordAuthentication no',
    subscribe  => File['/etc/ssh/sshd_config'],
    notify     => Service['ssh'],
  }

  service { 'ssh':
    ensure     => running,
    subscribe  => File['/etc/ssh/sshd_config'],
  }
}
