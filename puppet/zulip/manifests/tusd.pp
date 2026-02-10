# @summary Provide the tusd service binary
#
class zulip::tusd {
  $version = $zulip::common::versions['tusd']['version']
  $bin = "/srv/zulip-tusd-${version}/tusd"

  # This tarball contains only a single file, which is extracted as $bin
  zulip::external_dep { 'tusd':
    version        => $version,
    url            => "https://github.com/tus/tusd/releases/download/v${version}/tusd_linux_${zulip::common::goarch}.tar.gz",
    tarball_prefix => "tusd_linux_${zulip::common::goarch}",
    bin            => [$bin],
    cleanup_after  => [Service[supervisor]],
  }
  file { '/usr/local/bin/tusd':
    ensure  => link,
    target  => $bin,
    require => File[$bin],
    before  => Exec['Cleanup tusd'],
  }
}
