# @summary Install Sentry pre/post deploy hooks
#
class zulip::hooks::sentry {
  include zulip::hooks::base
  include zulip::sentry_cli

  zulip::hooks::file { [
    'common/sentry.sh',
    'pre-deploy.d/sentry.hook',
    'post-deploy.d/sentry.hook',
  ]: }
}
