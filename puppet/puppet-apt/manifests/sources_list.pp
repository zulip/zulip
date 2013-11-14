define apt::sources_list (
  $ensure  = present,
  $source  = false,
  $content = false
) {

  if $source {
    file {"/etc/apt/sources.list.d/${name}.list":
      ensure => $ensure,
      source => $source,
      owner => "root",
      group => "root",
      before => Exec['apt-get_update'],
      notify => Exec['apt-get_update'],
    }
  } else {
    file {"/etc/apt/sources.list.d/${name}.list":
      ensure  => $ensure,
      content => $content,
      owner => "root",
      group => "root",
      before  => Exec['apt-get_update'],
      notify  => Exec['apt-get_update'],
    }
  }

}
