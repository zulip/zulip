# globals
Exec { path => "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" }

class humbug {
  Exec { path => "/usr/sbin:/usr/bin:/sbin:/bin" }

  class {'apt': }
  class {'apt::backports':
    priority => 600
  }
}
