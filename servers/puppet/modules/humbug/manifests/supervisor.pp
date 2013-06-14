class humbug::supervisor {
  $supervisor_packages = [ "supervisor",]
  package { $supervisor_packages: ensure => "installed" }

  service { "supervisor":
    ensure => running,
    require => [File["/var/log/humbug"],
                Package["supervisor"],
                ],
  }
}
