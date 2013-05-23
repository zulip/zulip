class humbug ($machinetype) {
  class { "humbug::$machinetype": }

  file { '/etc/humbug-machinetype':
    ensure  => file,
    mode    => 644,
    content => "$machinetype\n",
  }

  Exec { path => "/usr/sbin:/usr/bin:/sbin:/bin" }

  class {'apt': }

}
