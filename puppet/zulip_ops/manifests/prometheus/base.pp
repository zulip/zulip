# @summary Configures a node for monitoring with Prometheus
#
class zulip_ops::prometheus::base {
  group { 'prometheus':
    ensure => present,
    gid    => '1060',
  }
  user { 'prometheus':
    ensure     => present,
    uid        => '1060',
    gid        => '1060',
    shell      => '/bin/bash',
    home       => '/nonexistent',
    managehome => false,
  }
}
