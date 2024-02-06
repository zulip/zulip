class kandra::firewall {
  package { 'iptables-persistent': }
  concat { '/etc/iptables/rules.v4':
    ensure  => present,
    mode    => '0600',
    require => Package['iptables-persistent'],
  }
  concat::fragment { 'iptables-header.v4':
    target => '/etc/iptables/rules.v4',
    source => 'puppet:///modules/kandra/iptables/header.v4',
    order  => '01',
  }
  concat::fragment { 'iptables-trailer.v4':
    target => '/etc/iptables/rules.v4',
    source => 'puppet:///modules/kandra/iptables/trailer.v4',
    order  => '99',
  }

  concat { '/etc/iptables/rules.v6':
    ensure  => present,
    mode    => '0600',
    require => Package['iptables-persistent'],
  }
  concat::fragment { 'iptables-header.v6':
    target => '/etc/iptables/rules.v6',
    source => 'puppet:///modules/kandra/iptables/header.v6',
    order  => '01',
  }
  concat::fragment { 'iptables-trailer.v6':
    target => '/etc/iptables/rules.v6',
    source => 'puppet:///modules/kandra/iptables/trailer.v6',
    order  => '99',
  }

  service { 'netfilter-persistent':
    ensure     => running,

    # Because there is no running process for this service, the normal status
    # checks fail.  Because Puppet then thinks the service has been manually
    # stopped, it won't restart it.  This fake status command will trick Puppet
    # into thinking the service is *always* running (which in a way it is, as
    # iptables is part of the kernel.)
    hasstatus  => true,
    status     => '/bin/true',

    # Under Debian, the "restart" parameter does not reload the rules, so tell
    # Puppet to fall back to stop/start, which does work.
    hasrestart => false,

    require    => Package['iptables-persistent'],
    subscribe  => [
      Concat['/etc/iptables/rules.v4'],
      Concat['/etc/iptables/rules.v6'],
    ],
  }
}
