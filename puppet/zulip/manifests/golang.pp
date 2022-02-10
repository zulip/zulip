# @summary go compiler and tools
#
class zulip::golang {
  $arch = $::architecture ? {
    'amd64'   => 'amd64',
    'aarch64' => 'arm64',
  }
  $version = $zulip::common::versions['golang']['version']

  $dir = "/srv/zulip-golang-${version}"
  $bin = "${dir}/bin/go"

  zulip::external_dep { 'golang':
    version        => $version,
    url            => "https://golang.org/dl/go${version}.linux-${arch}.tar.gz",
    tarball_prefix => 'go',
  }
}
