class zulip_ops::firewall {
  package { 'iptables-persistent': }
  file { '/etc/iptables/rules.v4':
    ensure  => file,
    mode    => '0600',
    content => template('zulip_ops/iptables/rules.v4.erb'),
    require => Package['iptables-persistent'],
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
    subscribe  => File['/etc/iptables/rules.v4'],
  }
}
