# @summary go compiler and tools
#
class zulip::golang {
  $version = '1.17.3'

  $dir = "/srv/zulip-golang-${version}/"
  $bin = "${dir}bin/go"

  zulip::sha256_tarball_to { 'golang':
    url     => "https://golang.org/dl/go${version}.linux-amd64.tar.gz",
    sha256  => '550f9845451c0c94be679faf116291e7807a8d78b43149f9506c1b15eb89008c',
    install => {
      'go/' => $dir,
    },
  }

  file { $bin:
    ensure  => file,
    require => Zulip::Sha256_tarball_to['golang'],
  }

  file { $dir:
    ensure  => directory,
    require => Zulip::Sha256_tarball_to['golang'],
  }

  unless $::operatingsystem == 'Ubuntu' and $::operatingsystemrelease == '18.04' {
    # Puppet 5.5.0 and below make this always-noisy, as they spout out
    # a notify line about tidying the managed directory above.  Skip
    # on Bionic, which has that old version; they'll get tidied upon
    # upgrade to 20.04.
    tidy { '/srv/zulip-golang-*':
      path    => '/srv/',
      recurse => 1,
      rmdirs  => true,
      matches => 'zulip-golang-*',
      require => File[$dir],
    }
  }
}
