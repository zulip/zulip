# @summary go compiler and tools
#
class zulip::golang {
  $version = $zulip::common::versions['golang']['version']

  $dir = "/srv/zulip-golang-${version}"
  $bin = "${dir}/bin/go"

  zulip::external_dep { 'golang':
    version        => $version,
    url            => "https://golang.org/dl/go${version}.linux-${::architecture}.tar.gz",
    tarball_prefix => 'go',
  }
}
