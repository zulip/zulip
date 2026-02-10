# @summary Install sentry-cli binary and pre/post deploy hooks
#
class zulip::hooks::base {
  file { [
    '/etc/zulip/hooks',
    '/etc/zulip/hooks/common',
    '/etc/zulip/hooks/pre-deploy.d',
    '/etc/zulip/hooks/post-deploy.d',
  ]:
    ensure => directory,
    owner  => 'zulip',
    group  => 'zulip',
    mode   => '0755',
    tag    => ['hooks'],
  }
}
