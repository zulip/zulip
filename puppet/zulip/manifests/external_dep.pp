define zulip::external_dep(
  String $version,
  String $sha256,
  String $url,
  String $tarball_prefix,
  String $bin = '',
) {

  $dir = "/srv/zulip-${title}-${version}/"

  zulip::sha256_tarball_to { $title:
    url     => $url,
    sha256  => $sha256,
    install => {
      $tarball_prefix => $dir,
    },
  }

  file { $dir:
    ensure  => directory,
    require => Zulip::Sha256_tarball_to[$title],
  }

  if $bin != '' {
    file { "${dir}${bin}":
      ensure  => file,
      require => File[$dir],
    }
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
