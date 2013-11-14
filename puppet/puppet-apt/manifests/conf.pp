define apt::conf($ensure, $content = false, $source = false) {
  if $content {
    file {"/etc/apt/apt.conf.d/${name}":
      ensure  => $ensure,
      content => $content,
      owner => "root",
      group => "root",
      before  => Exec['apt-get_update'],
      notify  => Exec['apt-get_update'],
    }
  }

  if $source {
    file {"/etc/apt/apt.conf.d/${name}":
      ensure => $ensure,
      source => $source,
      owner => "root",
      group => "root",
      before => Exec['apt-get_update'],
      notify => Exec['apt-get_update'],
    }
  }
}
