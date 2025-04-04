# @summary zulip_notify common file
#
class zulip::hooks::zulip_common {
  include zulip::hooks::base

  zulip::hooks::file { 'common/zulip_notify.sh': }
}
