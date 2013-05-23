class humbug::base {
  $packages = [ "screen", "strace", "vim", "emacs23-nox", "git", "python-tz",
                "sqlite3", "ntp", "python-simplejson", "host",
                "openssh-server", "python-pip", "puppet-el",
                "iptables-persistent", "nagios-plugins-basic", "munin-node",
                "munin-plugins-extra" ]
  package { $packages: ensure => "installed" }


  apt::key {"E5FB045CA79AA8FC25FDE9F3B4F81D07A529EF65":
    source  =>  "http://apt.humbughq.com/ops.asc",
  }
  apt::sources_list {"humbug":
    ensure  => present,
    content => 'deb http://apt.humbughq.com/ops wheezy main',
  }

  # FIXME: Stop using pip since it is insecure
  exec {"pip":
    command  => "/usr/bin/pip install django-jstemplate",
    creates  => "/usr/local/lib/python2.6/dist-packages/jstemplate",
    require  => Package['python-pip'],
  }
  exec {"pip2":
    command  => "/usr/bin/pip install markdown",
    creates  => "/usr/local/lib/python2.6/dist-packages/markdown",
    require  => Package['python-pip'],
  }
  exec {"pip3":
    command  => "/usr/bin/pip install requests",
    creates  => "/usr/local/lib/python2.6/dist-packages/requests",
    require  => Package['python-pip'],
  }
  exec {"pip4":
    command  => "/usr/bin/pip install pika",
    creates  => "/usr/local/lib/python2.6/dist-packages/pika",
    require  => Package['python-pip'],
  }
  exec {"pip5":
    command  => "/usr/bin/pip install South",
    creates  => "/usr/local/lib/python2.6/dist-packages/south",
    require  => Package['python-pip'],
  }
  exec {"pip6":
    command  => "/usr/bin/pip install django-bitfield",
    creates  => "/usr/local/lib/python2.6/dist-packages/bitfield",
    require  => Package['python-pip'],
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
    source     => 'puppet:///modules/humbug/authorized_keys',
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
    source     => 'puppet:///modules/humbug/root_authorized_keys',
  }

  # This is just an empty file.  It's used by the app to test if it's running
  # in production.
  file { '/etc/humbug-server':
    ensure     => file,
    mode       => 644,
    source     => 'puppet:///modules/humbug/humbug-server',
  }

  file { '/etc/puppet/puppet.conf':
    ensure     => file,
    mode       => 640,
    source     => 'puppet:///modules/humbug/puppet.conf',
  }

  file { '/etc/iptables/rules':
    ensure     => file,
    mode       => 600,
    source     => 'puppet:///modules/humbug/iptables/rules',
    require    => Package['iptables-persistent'],
  }

  file { '/etc/apt/apt.conf.d/02periodic':
    ensure     => file,
    mode       => 644,
    source     => 'puppet:///modules/humbug/apt/apt.conf.d/02periodic',
  }

  file { '/etc/ssh/sshd_config':
    require    => Package['openssh-server'],
    ensure     => file,
    source     => 'puppet:///modules/humbug/sshd_config',
    owner      => 'root',
    group      => 'root',
    mode       => 644,
  }

  service { 'ssh':
    ensure     => running,
    subscribe  => File['/etc/ssh/sshd_config'],
  }

  service { 'iptables-persistent':
    ensure     => running,
    subscribe  => File['/etc/iptables/rules'],
  }
}
