# @summary Send zuip update announcements after deploy
#
class zulip::hooks::send_zulip_update_announcements {
  include zulip::hooks::base

  zulip::hooks::file { [
    'post-deploy.d/send_zulip_update_announcements.hook',
  ]: }
}
