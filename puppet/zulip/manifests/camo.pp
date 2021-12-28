class zulip::camo (String $listen_address = '0.0.0.0') {
  # TODO/compatibility: Removed 2021-11 in version 5.0; these lines
  # can be removed once one must have upgraded through Zulip 5.0 or
  # higher to get to the next release.
  package { 'camo':
    ensure => 'purged',
  }

  $version = $zulip::common::versions['go-camo']['version']
  $dir = "/srv/zulip-go-camo-${version}"
  $bin = "${dir}/bin/go-camo"

  zulip::external_dep { 'go-camo':
    version        => $version,
    url            => "https://github.com/cactus/go-camo/releases/download/v${version}/go-camo-${version}.go1171.linux-${::architecture}.tar.gz",
    tarball_prefix => "go-camo-${version}",
  }

  file { "${zulip::common::supervisor_conf_dir}/go-camo.conf":
    ensure  => file,
    require => [
      Package['camo'],
      Package[supervisor],
      Zulip::External_Dep['go-camo'],
      File['/usr/local/bin/secret-env-wrapper'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/supervisor/go-camo.conf.erb'),
    notify  => Service[supervisor],
  }
}
