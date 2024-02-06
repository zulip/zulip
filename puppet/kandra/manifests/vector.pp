# @summary Installs Vector to transform Prometheus data
#
class kandra::vector {
  $version = $zulip::common::versions['vector']['version']
  $dir = "/srv/zulip-vector-${version}"
  $bin = "${dir}/bin/vector"

  $arch = $::os['architecture'] ? {
    'amd64'   => 'x86_64',
    'aarch64' => 'aarch64',
  }

  zulip::external_dep { 'vector':
    version        => $version,
    url            => "https://packages.timber.io/vector/${version}/vector-${version}-${arch}-unknown-linux-gnu.tar.gz",
    tarball_prefix => "vector-${arch}-unknown-linux-gnu",
  }
}
