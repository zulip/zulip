define zulip::external_dep(
  String $version,
  String $url,
  String $tarball_prefix = '',
  String $sha256 = '',
  String $mode = '0755',
  Array[String] $bin = [],
  Array[Type[Resource]] $cleanup_after = [],
) {
  $arch = $facts['os']['architecture']
  if $sha256 == '' {
    if $zulip::common::versions[$title]['sha256'] =~ Hash {
      $sha256_filled = $zulip::common::versions[$title]['sha256'][$arch]
      if $sha256_filled == undef {
        err("No sha256 found for ${title} for architecture ${arch}")
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
      notify     => Exec["Cleanup ${title}"],
    }
    file { $path:
      ensure  => file,
      require => Zulip::Sha256_File_To[$title],
      before  => Exec["Cleanup ${title}"],
      mode    => $mode,
    }
  } else {
    zulip::sha256_tarball_to { $title:
      url          => $url,
      sha256       => $sha256_filled,
      install_from => $tarball_prefix,
      install_to   => $path,
      notify       => Exec["Cleanup ${title}"],
    }
    file { $path:
      ensure  => present,
      require => Zulip::Sha256_Tarball_To[$title],
      before  => Exec["Cleanup ${title}"],
    }
    file { $bin:
      ensure  => file,
      require => [File[$path], Zulip::Sha256_Tarball_To[$title]],
      before  => Exec["Cleanup ${title}"],
      mode    => $mode,
    }
  }

  exec { "Cleanup ${title}":
    refreshonly => true,
    provider    => shell,
    onlyif      => "ls -d /srv/zulip-${title}-* | grep -xv '${path}'",
    command     => "ls -d /srv/zulip-${title}-* | grep -xv '${path}' | xargs rm -r",
    require     => $cleanup_after,
  }
}
