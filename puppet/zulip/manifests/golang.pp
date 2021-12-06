# @summary go compiler and tools
#
class zulip::golang {
  $version = '1.17.3'

  $dir = "/srv/zulip-golang-${version}/"
  $bin = "${dir}bin/go"

  zulip::external_dep { 'golang':
    version        => $version,
    url            => "https://golang.org/dl/go${version}.linux-${::architecture}.tar.gz",
    sha256         => '550f9845451c0c94be679faf116291e7807a8d78b43149f9506c1b15eb89008c',
    tarball_prefix => 'go/',
    bin            => 'bin/go',
  }
}
