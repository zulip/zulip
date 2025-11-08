# @summary Install hook that notifies when a deploy starts/stops
#
class zulip::hooks::zulip_notify {
  include zulip::hooks::base
  include zulip::hooks::zulip_common

  zulip::hooks::file { [
    'pre-deploy.d/zulip_notify.hook',
    'post-deploy.d/zulip_notify.hook',
  ]: }
}
