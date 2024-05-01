class zulip::smokescreen {
  include zulip::supervisor
  include zulip::golang

  $version = $zulip::common::versions['smokescreen-src']['version']
  $dir = "/srv/zulip-smokescreen-src-${version}"
  $bin = "/usr/local/bin/smokescreen-${version}-go-${zulip::golang::version}"

  zulip::external_dep { 'smokescreen-src':
    version        => $version,
    url            => "https://github.com/stripe/smokescreen/archive/${version}.tar.gz",
    tarball_prefix => "smokescreen-${version}",
  }

  exec { 'compile smokescreen':
    command     => "${zulip::golang::bin} build -o ${bin}",
    cwd         => $dir,
    # GOCACHE is required; nothing is written to GOPATH, but it is required to be set
    environment => ['GOCACHE=/tmp/gocache', 'GOPATH=/root/go'],
    creates     => $bin,
    require     => [
      Zulip::External_Dep['golang'],
      Zulip::External_Dep['smokescreen-src'],
    ],
  }
  # This resource is created by the 'compile smokescreen' step.
  file { $bin:
    ensure  => file,
    require => Exec['compile smokescreen'],
  }
  exec { 'Cleanup smokescreen':
    refreshonly => true,
    provider    => shell,
    onlyif      => "ls /usr/local/bin/smokescreen-* | grep -xv '${bin}'",
    command     => "ls /usr/local/bin/smokescreen-* | grep -xv '${bin}' | xargs rm -r",
    require     => [File[$bin], Service[supervisor]],
  }

  $listen_address = zulipconf('http_proxy', 'listen_address', '127.0.0.1')
  file { "${zulip::common::supervisor_conf_dir}/smokescreen.conf":
    ensure  => file,
    require => [
      Package[supervisor],
      Exec['compile smokescreen'],
    ],
    owner   => 'root',
    group   => 'root',
    mode    => '0644',
    content => template('zulip/supervisor/smokescreen.conf.erb'),
    notify  => Service[supervisor],
  }

  file { '/etc/logrotate.d/smokescreen':
    ensure => file,
    owner  => 'root',
    group  => 'root',
    mode   => '0644',
    source => 'puppet:///modules/zulip/logrotate/smokescreen',
  }
}
