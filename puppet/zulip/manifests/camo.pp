class zulip::camo (String $listen_address = '0.0.0.0') {
  # TODO/compatibility: Removed 2021-11 in version 5.0; these lines
  # can be removed once one must have upgraded through Zulip 5.0 or
  # higher to get to the next release.
  package { 'camo':
    ensure => purged,
  }

  $version = $zulip::common::versions['go-camo']['version']
  $goversion = $zulip::common::versions['go-camo']['goversion']
  $dir = "/srv/zulip-go-camo-${version}"
  $bin = "${dir}/bin/go-camo"

  zulip::external_dep { 'go-camo':
    version        => $version,
    url            => "https://github.com/cactus/go-camo/releases/download/v${version}/go-camo-${version}.go${goversion}.linux-${zulip::common::goarch}.tar.gz",
    tarball_prefix => "go-camo-${version}",
    bin            => [$bin],
    cleanup_after  => [Service[supervisor]],
  }

  # We would like to not waste resources by going through Smokescreen,
  # as go-camo already prohibits private-IP access; but a
  # non-Smokescreen exit proxy may be required to access the public
  # Internet.  The `enable_for_camo` flag, if it exists, can override
  # our guess, in either direction.
  $proxy_host = zulipconf('http_proxy', 'host', 'localhost')
  $proxy_port = zulipconf('http_proxy', 'port', '4750')
  $proxy_is_smokescreen = ($proxy_host in ['localhost', '127.0.0.1', '::1']) and ($proxy_port == '4750')
  $camo_use_proxy = zulipconf('http_proxy', 'enable_for_camo', !$proxy_is_smokescreen)
  if $camo_use_proxy {
    if $proxy_is_smokescreen {
      include zulip::smokescreen
    }

    if $proxy_host != '' and $proxy_port != '' {
      $proxy = "http://${proxy_host}:${proxy_port}"
    } else {
      $proxy = ''
    }
  } else {
    $proxy = ''
  }

  file { "${zulip::common::supervisor_conf_dir}/go-camo.conf":
    ensure  => file,
    require => [
      Package['camo'],
      Package[supervisor],
      File[$bin],
      File['/usr/local/bin/secret-env-wrapper'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/supervisor/go-camo.conf.erb'),
    notify  => Service[supervisor],
  }
}
