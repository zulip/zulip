define zulip::external_dep(
  String $version,
  String $url,
  String $tarball_prefix = '',
  String $sha256 = '',
  String $mode = '0755',
) {
  if $sha256 == '' {
    if $zulip::common::versions[$title]['sha256'] =~ Hash {
      $sha256_filled = $zulip::common::versions[$title]['sha256'][$::os['architecture']]
      if $sha256_filled == undef {
        err("No sha256 found for ${title} for architecture ${::os['architecture']}")
        fail()
      }
    } else {
      # For things like source code which are arch-invariant
      $sha256_filled = $zulip::common::versions[$title]['sha256']
    }
  } else {
    $sha256_filled = $sha256
  }

  $path = "/srv/zulip-${title}-${version}"

  if $tarball_prefix == '' {
    zulip::sha256_file_to { $title:
      url        => $url,
      sha256     => $sha256_filled,
      install_to => $path,
      before     => File[$path],
    }
    file { $path:
      ensure => file,
      mode   => $mode,
    }
  } else {
    zulip::sha256_tarball_to { $title:
      url          => $url,
      sha256       => $sha256_filled,
      install_from => $tarball_prefix,
      install_to   => $path,
      before       => File[$path],
    }
    file { $path:
      ensure => present,
    }
  }


  tidy { "/srv/zulip-${title}-*":
    path    => '/srv/',
    recurse => 1,
    rmdirs  => true,
    matches => "zulip-${title}-*",
    require => File[$path],
  }
}
