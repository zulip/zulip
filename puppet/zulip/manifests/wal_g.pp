# @summary Provide the wal-g and env-wal-g binaries.
#
class zulip::wal_g {
  $wal_g_version = $zulip::common::versions['wal-g']['version']
  $wal_g_binary_hash = $zulip::common::versions['wal-g']['sha256'][$::os['architecture']]
  $wal_g_commit_id = $zulip::common::versions['wal-g']['git_commit_id']
  $bin = "/srv/zulip-wal-g-${wal_g_version}"

  if $wal_g_binary_hash != undef {
    # We have a binary for this arch
    $package = "wal-g-pg-ubuntu-20.04-${zulip::common::goarch}"
    # This tarball contains only a single file, which is extracted as $bin
    zulip::external_dep { 'wal-g':
      version        => $wal_g_version,
      url            => "https://github.com/wal-g/wal-g/releases/download/v${wal_g_version}/${package}.tar.gz",
      tarball_prefix => $package,
      before         => File['/usr/local/bin/wal-g'],
    }
  } else {
    include zulip::golang
    $source_dir = "/srv/zulip-wal-g-src-${wal_g_version}"
    exec { 'clone wal-g':
      command => "git clone https://github.com/wal-g/wal-g.git --branch v${wal_g_version} ${source_dir}",
      cwd     => '/srv',
      creates => $source_dir,
      require => Package['git'],
    }
    exec { 'compile wal-g':
      command     => "${::zulip_scripts_path}/lib/build-wal-g ${wal_g_version} ${wal_g_commit_id}",
      environment => ["GOBIN=${zulip::golang::dir}/bin"],
      cwd         => $source_dir,
      creates     => $bin,
      require     => [
        Zulip::External_Dep['golang'],
        Exec['clone wal-g'],
      ],
      timeout     => 600,
      before      => File['/usr/local/bin/wal-g'],
    }
    tidy { '/srv/zulip-wal-g-*':
      path    => '/srv/',
      recurse => 1,
      rmdirs  => true,
      matches => 'zulip-wal-g-*',
      require => Exec['compile wal-g'],
    }
  }
  file { '/usr/local/bin/wal-g':
    ensure => link,
    target => $bin,
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
