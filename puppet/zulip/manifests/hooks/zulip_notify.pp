# @summary Install hook that notifies when a deploy starts/stops
#
class zulip::hooks::zulip_notify {
  include zulip::hooks::base

  zulip::hooks::file { [
    'common/zulip_notify.sh',
    'pre-deploy.d/zulip_notify.hook',
    'post-deploy.d/zulip_notify.hook',
  ]: }
}
