# @summary go compiler and tools
#
class zulip::golang {
  $version = $zulip::common::versions['golang']['version']
  $dir = "/srv/zulip-golang-${version}"
  $bin = "${dir}/bin/go"

  zulip::external_dep { 'golang':
    version        => $version,
    url            => "https://go.dev/dl/go${version}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => 'go',
  }
}
