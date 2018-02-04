# ppa.pp

define apt::ppa(
  $release = $::lsbdistcodename,
  $options = '-y'
) {
  include apt::params
  include apt::update

  $sources_list_d = $apt::params::sources_list_d

  if ! $release {
    fail('lsbdistcodename fact not available: release parameter required')
  }

  $filename_without_slashes = regsubst($name, '/', '-', 'G')
  $filename_without_dots    = regsubst($filename_without_slashes, '\.', '_', 'G')
  $filename_without_ppa     = regsubst($filename_without_dots, '^ppa:', '', 'G')
  $sources_list_d_filename  = "${filename_without_ppa}-${release}.list"

  $package = $::lsbdistrelease ? {
    /^[1-9]\..*|1[01]\..*|12.04$/ => 'python-software-properties',
    default  => 'software-properties-common',
  }

  if ! defined(Package[$package]) {
    package { $package: }
  }

  if defined(Class[apt]) {
    $proxy_host = getparam(Class[apt], 'proxy_host')
    $proxy_port = getparam(Class[apt], 'proxy_port')
    case  $proxy_host {
      false, '': {
        $proxy_env = []
      }
      default: {$proxy_env = ["http_proxy=http://${proxy_host}:${proxy_port}", "https_proxy=http://${proxy_host}:${proxy_port}"]}
    }
  } else {
    $proxy_env = []
  }
  exec { "add-apt-repository-${name}":
    environment  => $proxy_env,
    command      => "/usr/bin/add-apt-repository ${options} ${name}",
    unless       => "/usr/bin/test -s ${sources_list_d}/${sources_list_d_filename}",
    logoutput    => 'on_failure',
    notify       => Exec['apt_update'],
    require      => [
      File[$sources_list_d],
      Package[$package],
    ],
  }

  file { "${sources_list_d}/${sources_list_d_filename}":
    ensure  => file,
    require => Exec["add-apt-repository-${name}"],
  }

  # Need anchor to provide containment for dependencies.
  anchor { "apt::ppa::${name}":
    require => Class['apt::update'],
  }
}
