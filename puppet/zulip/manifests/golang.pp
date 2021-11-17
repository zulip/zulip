# @summary go compiler and tools
#
class zulip::golang {
  $golang_version = '1.16.4'
  zulip::sha256_tarball_to { 'golang':
    url     => "https://golang.org/dl/go${golang_version}.linux-amd64.tar.gz",
    sha256  => '7154e88f5a8047aad4b80ebace58a059e36e7e2e4eb3b383127a28c711b4ff59',
    install => {
      'go/' => "/srv/golang-${golang_version}/",
    },
  }

  file { '/srv/golang':
    ensure  => 'link',
    target  => "/srv/golang-${golang_version}/",
    require => Zulip::Sha256_tarball_to['golang'],
  }
}
