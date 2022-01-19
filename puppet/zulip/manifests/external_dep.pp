define zulip::external_dep(
  String $version,
  String $url,
  String $tarball_prefix,
  String $sha256 = '',
) {
  if $sha256 == '' {
    if $zulip::common::versions[$title]['sha256'] =~ Hash {
      $sha256_filled = $zulip::common::versions[$title]['sha256'][$::architecture]
      if $sha256_filled == undef {
        err("No sha256 found for ${title} for architecture ${::architecture}")
        fail()
      }
    } else {
      # For things like source code which are arch-invariant
      $sha256_filled = $zulip::common::versions[$title]['sha256']
    }
  } else {
    $sha256_filled = $sha256
  }

  $dir = "/srv/zulip-${title}-${version}"

  zulip::sha256_tarball_to { $title:
    url     => $url,
    sha256  => $sha256_filled,
    install => {
      $tarball_prefix => $dir,
    },
  }

  file { $dir:
    ensure  => present,
    require => Zulip::Sha256_Tarball_To[$title],
  }

  unless $::operatingsystem == 'Ubuntu' and $::operatingsystemrelease == '18.04' {
    # Puppet 5.5.0 and below make this always-noisy, as they spout out
    # a notify line about tidying the managed directory above.  Skip
    # on Bionic, which has that old version; they'll get tidied upon
    # upgrade to 20.04.
    tidy { "/srv/zulip-${title}-*":
      path    => '/srv/',
      recurse => 1,
      rmdirs  => true,
      matches => "zulip-${title}-*",
      require => File[$dir],
    }
  }
}
