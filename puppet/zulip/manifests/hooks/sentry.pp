# @summary Install sentry-cli binary and pre/post deploy hooks
#
class zulip::hooks::sentry {
  include zulip::hooks::base
  $version = $zulip::common::versions['sentry-cli']['version']
  $bin = "/srv/zulip-sentry-cli-${version}"

  $arch = $::os['architecture'] ? {
    'amd64'   => 'x86_64',
    'aarch64' => 'aarch64',
  }

  zulip::external_dep { 'sentry-cli':
    version => $version,
    url     => "https://downloads.sentry-cdn.com/sentry-cli/${version}/sentry-cli-Linux-${arch}",
  }

  file { '/usr/local/bin/sentry-cli':
    ensure => link,
    target => $bin,
  }

  zulip::hooks::file { [
    'common/sentry.sh',
    'pre-deploy.d/sentry.hook',
    'post-deploy.d/sentry.hook',
  ]: }
}
