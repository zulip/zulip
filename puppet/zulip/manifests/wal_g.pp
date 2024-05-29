# @summary Provide the wal-g and env-wal-g binaries.
#
class zulip::wal_g {
  $wal_g_version = $zulip::common::versions['wal-g']['version']
  $bin = "/srv/zulip-wal-g-${wal_g_version}"

  # For unfathomable reasons, the amd64 and aarch64 builds have slightly different shaped URLs
  if $zulip::common::goarch == 'amd64' {
    $package = "wal-g-pg-ubuntu-20.04-${zulip::common::goarch}"
  } else {
    $package = "wal-g-pg-ubuntu20.04-${zulip::common::goarch}"
  }
  # This tarball contains only a single file, which is extracted as $bin
  zulip::external_dep { 'wal-g':
    version        => $wal_g_version,
    url            => "https://github.com/wal-g/wal-g/releases/download/v${wal_g_version}/${package}.tar.gz",
    tarball_prefix => $package,
  }
  file { '/usr/local/bin/wal-g':
    ensure  => link,
    target  => $bin,
    require => File[$bin],
    before  => Exec['Cleanup wal-g'],
  }
  # We used to install versions into /usr/local/bin/wal-g-VERSION,
  # until we moved to using Zulip::External_Dep which places them in
  # /srv/zulip-wal-g-VERSION.  Tidy old versions.
  tidy { '/usr/local/bin/wal-g-*':
    recurse => 1,
    path    => '/usr/local/bin/',
    matches => 'wal-g-*',
  }

  file { '/usr/local/bin/env-wal-g':
    ensure  => file,
    owner   => 'root',
    group   => 'root',
    mode    => '0755',
    source  => 'puppet:///modules/zulip/postgresql/env-wal-g',
    require => [
      File['/usr/local/bin/wal-g'],
    ],
  }
}
