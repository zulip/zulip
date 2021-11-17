# @summary go compiler and tools
#
class zulip::golang {
  $version = '1.17.3'

  $dir = "/srv/golang-${version}/"
  $bin = '/srv/golang/bin/go'

  zulip::sha256_tarball_to { 'golang':
    url     => "https://golang.org/dl/go${version}.linux-amd64.tar.gz",
    sha256  => '550f9845451c0c94be679faf116291e7807a8d78b43149f9506c1b15eb89008c',
    install => {
      'go/' => $dir,
    },
  }

  file { '/srv/golang':
    ensure  => 'link',
    target  => $dir,
    require => Zulip::Sha256_tarball_to['golang'],
  }
}
