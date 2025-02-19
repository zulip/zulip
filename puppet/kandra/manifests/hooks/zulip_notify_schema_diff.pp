# @summary Install hook that checks for schema drift from published ref
#
class kandra::hooks::zulip_notify_schema_diff {
  include zulip::hooks::base
  include zulip::hooks::zulip_common

  kandra::hooks::file { 'post-deploy.d/zulip_notify_schema_diff.hook': }
}
