class humbug {
  Exec { path => "/usr/sbin:/usr/bin:/sbin:/bin" }

  class {'apt': }
  class {'apt::backports':
    priority => 600
  }
}
