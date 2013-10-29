class zulip-internal ($machinetype) {
  class { "zulip-internal::$machinetype": }

  file { '/etc/zulip/machinetype':
    ensure  => file,
    mode    => 644,
    content => "$machinetype\n",
  }

  Exec { path => "/usr/sbin:/usr/bin:/sbin:/bin" }

  class {'apt': }

}
