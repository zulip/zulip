# source.pp
# add an apt source

define apt::source(
  $ensure            = present,
  $location          = '',
  $release           = 'UNDEF',
  $repos             = 'main',
  $include_src       = true,
  $required_packages = false,
  $key               = false,
  $key_server        = 'keyserver.ubuntu.com',
  $key_content       = false,
  $key_source        = false,
  $pin               = false,
  $architecture      = undef
) {

  include apt::params
  include apt::update

  $sources_list_d = $apt::params::sources_list_d
  $provider       = $apt::params::provider

  if $release == 'UNDEF' {
    if $::lsbdistcodename == undef {
      fail('lsbdistcodename fact not available: release parameter required')
    } else {
      $release_real = $::lsbdistcodename
    }
  } else {
    $release_real = $release
  }

  file { "${name}.list":
    ensure  => $ensure,
    path    => "${sources_list_d}/${name}.list",
    owner   => root,
    group   => root,
    mode    => '0644',
    content => template("${module_name}/source.list.erb"),
    notify  => Exec['apt_update'],
  }


  if ($pin != false) {
    # Get the host portion out of the url so we can pin to origin
    $url_split = split($location, '/')
    $host      = $url_split[2]

    apt::pin { $name:
      ensure   => $ensure,
      priority => $pin,
      before   => File["${name}.list"],
      origin   => $host,
    }
  }

  if ($required_packages != false) and ($ensure == 'present') {
    exec { "Required packages: '${required_packages}' for ${name}":
      command     => "${provider} -y install ${required_packages}",
      logoutput   => 'on_failure',
      refreshonly => true,
      subscribe   => File["${name}.list"],
      before      => Exec['apt_update'],
    }
  }

  # We do not want to remove keys when the source is absent.
  if ($key != false) and ($ensure == 'present') {
    apt::key { "Add key: ${key} from Apt::Source ${title}":
      ensure      => present,
      key         => $key,
      key_server  => $key_server,
      key_content => $key_content,
      key_source  => $key_source,
      before      => File["${name}.list"],
    }
  }

  # Need anchor to provide containment for dependencies.
  anchor { "apt::source::${name}":
    require => Class['apt::update'],
  }
}
