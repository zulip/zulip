# @summary Install sentry-cli binary
#
class zulip::sentry_cli {
  $version = $zulip::common::versions['sentry-cli']['version']
  $bin = "/srv/zulip-sentry-cli-${version}"

  $arch = $facts['os']['architecture'] ? {
    'amd64'   => 'x86_64',
    'aarch64' => 'aarch64',
  }

  zulip::external_dep { 'sentry-cli':
    version => $version,
    url     => "https://downloads.sentry-cdn.com/sentry-cli/${version}/sentry-cli-Linux-${arch}",
  }

  file { '/usr/local/bin/sentry-cli':
    ensure  => link,
    target  => $bin,
    require => File[$bin],
    before  => Exec['Cleanup sentry-cli'],
  }
}
